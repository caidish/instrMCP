"""
General test instrument simulator for QCoDeS.

This module provides a flexible, JSON-configurable test instrument that can simulate
various types of devices with independent and dependent parameters, data interpolation,
and derived parameter calculations.
"""

import json
import numpy as np
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Callable
import logging

try:
    import qcodes as qc
    from qcodes import Parameter
    from qcodes.instrument_drivers.mock_instruments import DummyBase
    from qcodes.validators import Numbers, Enum
    HAS_QCODES = True
except ImportError:
    HAS_QCODES = False

try:
    from scipy.interpolate import RegularGridInterpolator
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

from ..MoTe2QAHE_instr.data_loader import MATFileLoader

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when there's an error in the JSON configuration."""
    pass


class GeneralTestInstrument(DummyBase):
    """General test instrument simulator configured via JSON files.
    
    This instrument can simulate various device types by loading configuration
    from JSON files that specify parameters, data files, and behavior.
    """
    
    def __init__(self, 
                 name: str,
                 config_file: str,
                 data_file_base_path: Optional[str] = None,
                 **kwargs):
        """Initialize the general test instrument.
        
        Args:
            name: Instrument name
            config_file: Path to JSON configuration file (supports ${VAR} environment variables)
            data_file_base_path: Base path for data files (supports ${VAR} environment variables)
            **kwargs: Additional arguments passed to DummyBase
            
        Note:
            Both config_file and data_file_base_path support environment variable expansion
            using ${VAR} or $VAR syntax (e.g., ${instrMCP_PATH}/config/file.json)
        """
        if not HAS_QCODES:
            raise ImportError("qcodes is required. Install with: pip install qcodes")
        if not HAS_SCIPY:
            raise ImportError("scipy is required. Install with: pip install scipy")
            
        # Load and validate configuration
        # Expand environment variables in file paths
        expanded_config_file = os.path.expandvars(config_file)
        self.config_file = Path(expanded_config_file)
        if not self.config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_file} (expanded: {expanded_config_file})")
            
        self.config = self._load_configuration()
        
        if data_file_base_path:
            expanded_base_path = os.path.expandvars(data_file_base_path)
            self.data_file_base_path = Path(expanded_base_path)
        else:
            self.data_file_base_path = self.config_file.parent
        
        # Initialize base class
        super().__init__(name, **kwargs)
        
        # Store parameter values
        self._parameter_values = {}
        self._interpolators = {}
        self._derived_calculators = {}
        
        # Load data and setup instrument
        self._load_data()
        self._setup_parameters()
        self._setup_interpolators()
        self._setup_derived_parameters()
        
        logger.info(f"General test instrument '{name}' initialized from {config_file} (expanded: {self.config_file})")
    
    def _load_configuration(self) -> Dict[str, Any]:
        """Load and validate JSON configuration."""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            
            # Basic validation
            required_sections = ['instrument_info', 'data_file', 'parameters']
            for section in required_sections:
                if section not in config:
                    raise ConfigurationError(f"Missing required section: {section}")
            
            # Validate parameters section
            if 'independent' not in config['parameters'] or 'dependent' not in config['parameters']:
                raise ConfigurationError("Parameters section must have 'independent' and 'dependent' keys")
            
            logger.debug(f"Configuration loaded successfully from {self.config_file}")
            return config
            
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON in configuration file: {e}")
        except Exception as e:
            raise ConfigurationError(f"Error loading configuration: {e}")
    
    def _load_data(self):
        """Load data file specified in configuration."""
        data_config = self.config['data_file']
        data_file_path = self.data_file_base_path / data_config['path']
        
        if not data_file_path.exists():
            raise FileNotFoundError(f"Data file not found: {data_file_path}")
        
        # Store interpolation settings
        self._interpolation_method = data_config.get('interpolation_method', 'linear')
        self._bounds_error = data_config.get('bounds_error', False)
        self._fill_value = data_config.get('fill_value', np.nan)
        
        # Load data using existing loader
        self._data_loader = MATFileLoader(str(data_file_path))
        self._data = self._data_loader.load_data()
        
        logger.info(f"Data loaded from {data_file_path}")
    
    def _setup_parameters(self):
        """Setup QCoDeS parameters from configuration."""
        
        # Setup independent (settable) parameters
        for param_config in self.config['parameters']['independent']:
            self._add_independent_parameter(param_config)
        
        # Setup dependent (gettable only) parameters  
        for param_config in self.config['parameters']['dependent']:
            self._add_dependent_parameter(param_config)
    
    def _add_independent_parameter(self, param_config: Dict[str, Any]):
        """Add an independent (settable) parameter."""
        name = param_config['name']
        
        # Create validator if specified
        validator = self._create_validator(param_config.get('validator'))
        
        # Store initial value
        initial_value = param_config.get('initial_value', 0.0)
        self._parameter_values[name] = initial_value
        
        # Create parameter
        self.add_parameter(
            name,
            label=param_config.get('label', name),
            unit=param_config.get('unit', ''),
            get_cmd=lambda n=name: self._get_independent_parameter(n),
            set_cmd=lambda val, n=name: self._set_independent_parameter(n, val),
            vals=validator,
            docstring=param_config.get('description', f'Independent parameter {name}')
        )
        
        # Add alias if specified
        if 'alias' in param_config:
            alias = param_config['alias']
            setattr(self, alias, getattr(self, name))
        
        logger.debug(f"Added independent parameter: {name}")
    
    def _add_dependent_parameter(self, param_config: Dict[str, Any]):
        """Add a dependent (read-only) parameter.""" 
        name = param_config['name']
        
        # Create parameter
        self.add_parameter(
            name,
            label=param_config.get('label', name),
            unit=param_config.get('unit', ''),
            get_cmd=lambda n=name: self._get_dependent_parameter(n),
            docstring=param_config.get('description', f'Dependent parameter {name}')
        )
        
        # Add alias if specified
        if 'alias' in param_config:
            alias = param_config['alias']
            setattr(self, alias, getattr(self, name))
        
        logger.debug(f"Added dependent parameter: {name}")
    
    def _create_validator(self, validator_config: Optional[Dict[str, Any]]):
        """Create a QCoDeS validator from configuration."""
        if not validator_config:
            return None
            
        validator_type = validator_config.get('type', 'numbers').lower()
        
        if validator_type == 'numbers':
            min_val = validator_config.get('min', -np.inf)
            max_val = validator_config.get('max', np.inf)
            return Numbers(min_val, max_val)
        elif validator_type == 'enum':
            values = validator_config.get('values', [])
            return Enum(*values)
        else:
            logger.warning(f"Unknown validator type: {validator_type}")
            return None
    
    def _setup_interpolators(self):
        """Create interpolators for dependent parameters."""
        dependent_params = self.config['parameters']['dependent']
        independent_param_names = [p['name'] for p in self.config['parameters']['independent']]
        
        # Get coordinate arrays from data
        coord_arrays = []
        coord_names = []
        sort_indices = []
        
        for param_name in independent_param_names:
            if param_name in self._data:
                coords = self._data[param_name]
                if not np.all(np.diff(coords) > 0):
                    # Sort if needed
                    sort_idx = np.argsort(coords)
                    coords = coords[sort_idx]
                    sort_indices.append(sort_idx)
                else:
                    sort_indices.append(None)
                coord_arrays.append(coords)
                coord_names.append(param_name)
        
        # Create interpolators for each dependent parameter
        for param_config in dependent_params:
            param_name = param_config['name']
            data_key = param_config.get('data_key', param_name)
            
            if data_key not in self._data:
                logger.warning(f"Data key '{data_key}' not found in data file for parameter '{param_name}'")
                continue
            
            # Use depends_on order if specified, otherwise use default independent parameter order
            param_depends_on = param_config.get('depends_on', independent_param_names)
            
            # Get coordinate arrays in the order specified by depends_on
            param_coord_arrays = []
            param_sort_indices = []
            for dep_param in param_depends_on:
                if dep_param in self._data:
                    coords = self._data[dep_param]
                    if not np.all(np.diff(coords) > 0):
                        sort_idx = np.argsort(coords)
                        coords = coords[sort_idx]
                        param_sort_indices.append(sort_idx)
                    else:
                        param_sort_indices.append(None)
                    param_coord_arrays.append(coords)
            
            data_array = self._data[data_key]
            
            # Sort data array to match coordinate sorting (using parameter-specific sorting)
            for i, sort_idx in enumerate(param_sort_indices):
                if sort_idx is not None:
                    # Apply sorting along the appropriate axis
                    if i == 0:  # First dimension (usually rows)
                        data_array = data_array[sort_idx, :]
                    elif i == 1:  # Second dimension (usually columns)
                        data_array = data_array[:, sort_idx]
            
            # Handle NaN values
            if np.any(~np.isfinite(data_array)):
                logger.warning(f"Found non-finite values in {param_name}, replacing with mean")
                finite_mask = np.isfinite(data_array)
                if np.any(finite_mask):
                    data_array = np.where(finite_mask, data_array, np.nanmean(data_array))
                else:
                    data_array = np.zeros_like(data_array)
            
            try:
                # Debug: Check array shapes
                logger.debug(f"Setting up interpolator for {param_name}:")
                logger.debug(f"  Coord shapes: {[arr.shape for arr in coord_arrays]}")
                logger.debug(f"  Data shape: {data_array.shape}")
                
                # Verify that data shape matches coordinate grid (using parameter-specific coordinates)
                param_expected_shape = tuple(len(coord) for coord in param_coord_arrays)
                if data_array.shape != param_expected_shape:
                    logger.warning(f"Data shape {data_array.shape} doesn't match expected {param_expected_shape}, attempting transpose")
                    if data_array.shape == param_expected_shape[::-1]:  # Try transpose
                        data_array = data_array.T
                        logger.debug(f"  Transposed data shape: {data_array.shape}")
                
                interpolator = RegularGridInterpolator(
                    points=tuple(param_coord_arrays),
                    values=data_array,
                    method=self._interpolation_method,
                    bounds_error=self._bounds_error,
                    fill_value=self._fill_value
                )
                self._interpolators[param_name] = interpolator
                logger.debug(f"Created interpolator for {param_name}")
                
            except Exception as e:
                logger.error(f"Failed to create interpolator for {param_name}: {e}")
                logger.debug(f"  Coord arrays: {[len(arr) for arr in coord_arrays]}")
                logger.debug(f"  Data array shape: {data_array.shape}")
                self._interpolators[param_name] = lambda pts: np.full(pts.shape[0], np.nan)
    
    def _setup_derived_parameters(self):
        """Setup derived parameter calculations."""
        if 'derived_parameters' not in self.config:
            return
        
        for param_config in self.config['derived_parameters']:
            name = param_config['name']
            formula = param_config.get('formula', '')
            
            # Create simple calculator (could be extended with expression parsing)
            calculator = self._create_derived_calculator(formula)
            self._derived_calculators[name] = calculator
            
            # Add as parameter
            self.add_parameter(
                name,
                label=param_config.get('label', name),
                unit=param_config.get('unit', ''),
                get_cmd=lambda n=name: self._get_derived_parameter(n),
                docstring=param_config.get('description', f'Derived parameter {name}')
            )
            
            # Add alias
            if 'alias' in param_config:
                alias = param_config['alias']
                setattr(self, alias, getattr(self, name))
    
    def _create_derived_calculator(self, formula: str) -> Callable[[], float]:
        """Create a calculator function for derived parameters."""
        # Simple implementation - could be extended with proper expression parsing
        if formula == "lockin_xx / lockin_i":
            return lambda: self._get_safe_division('lockin_xx', 'lockin_i')
        elif formula == "lockin_i / lockin_xx":
            return lambda: self._get_safe_division('lockin_i', 'lockin_xx')
        elif formula == "lockin_xy / lockin_i":
            return lambda: self._get_safe_division('lockin_xy', 'lockin_i')
        else:
            logger.warning(f"Unknown formula: {formula}")
            return lambda: np.nan
    
    def _get_safe_division(self, numerator: str, denominator: str) -> float:
        """Safely divide two parameters, handling zero division."""
        try:
            num_val = self._get_dependent_parameter(numerator)
            den_val = self._get_dependent_parameter(denominator) 
            
            if abs(den_val) < 1e-20:  # Avoid division by zero
                return np.inf if num_val > 0 else -np.inf if num_val < 0 else np.nan
            
            return float(num_val / den_val)
        except Exception as e:
            logger.error(f"Error in safe division {numerator}/{denominator}: {e}")
            return np.nan
    
    # Parameter getter/setter methods
    def _get_independent_parameter(self, name: str) -> float:
        """Get value of an independent parameter."""
        return self._parameter_values.get(name, 0.0)
    
    def _set_independent_parameter(self, name: str, value: float):
        """Set value of an independent parameter."""
        self._parameter_values[name] = float(value)
        logger.debug(f"Set {name} = {value}")
    
    def _get_dependent_parameter(self, name: str) -> float:
        """Get interpolated value of a dependent parameter."""
        if name not in self._interpolators:
            logger.error(f"No interpolator available for parameter {name}")
            return np.nan
        
        try:
            # Find the parameter configuration to get depends_on order
            param_config = None
            for param in self.config['parameters']['dependent']:
                if param['name'] == name:
                    param_config = param
                    break
            
            if param_config is None:
                logger.error(f"Parameter configuration not found for {name}")
                return np.nan
            
            # Get depends_on order, or use default independent parameter order
            independent_param_names = [p['name'] for p in self.config['parameters']['independent']]
            depends_on = param_config.get('depends_on', independent_param_names)
            
            # Get current values in the correct order
            point_values = [self._parameter_values.get(param, 0.0) for param in depends_on]
            
            # Interpolate
            point = np.array([point_values])
            result = self._interpolators[name](point)
            return float(result[0])
            
        except Exception as e:
            logger.error(f"Interpolation failed for {name}: {e}")
            return np.nan
    
    def _get_derived_parameter(self, name: str) -> float:
        """Get calculated value of a derived parameter."""
        if name not in self._derived_calculators:
            logger.error(f"No calculator available for derived parameter {name}")
            return np.nan
        
        try:
            return self._derived_calculators[name]()
        except Exception as e:
            logger.error(f"Calculation failed for derived parameter {name}: {e}")
            return np.nan
    
    def get_idn(self) -> Dict[str, Optional[str]]:
        """Override get_idn with info from configuration."""
        info = self.config['instrument_info']
        return {
            "vendor": info.get('vendor', 'General Test Instrument'),
            "model": info.get('model', 'GeneralTest'),
            "serial": self.name,
            "firmware": info.get('firmware', '1.0.0')
        }
    
    def set_independent_values(self, **values) -> Dict[str, float]:
        """Set multiple independent parameters and return all measurements.
        
        Args:
            **values: Parameter name-value pairs
            
        Returns:
            Dictionary with all parameter values
        """
        # Set independent parameters
        for param_name, value in values.items():
            if hasattr(self, param_name):
                getattr(self, param_name)(value)
        
        # Get all parameter values
        result = {}
        for param in self.parameters:
            if param != 'IDN':  # Skip IDN
                try:
                    result[param] = getattr(self, param)()
                except:
                    result[param] = np.nan
        
        return result
    
    def get_configuration_summary(self) -> Dict[str, Any]:
        """Get a summary of the instrument configuration."""
        return {
            'config_file': str(self.config_file),
            'instrument_info': self.config['instrument_info'],
            'independent_parameters': [p['name'] for p in self.config['parameters']['independent']],
            'dependent_parameters': [p['name'] for p in self.config['parameters']['dependent']],
            'derived_parameters': [p['name'] for p in self.config.get('derived_parameters', [])],
            'data_file': self.config['data_file'],
            'metadata': self.config.get('metadata', {})
        }