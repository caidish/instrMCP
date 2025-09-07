"""
QCoDeS instrument simulator for MoTe2 QAHE device.

Provides a local instrument that interpolates measurement data based on gate voltages.
"""

import numpy as np
from typing import Optional, Dict, Any, Union
import logging

try:
    import qcodes as qc
    from qcodes import Parameter
    from qcodes.parameters import DelegateParameter
    from qcodes.instrument_drivers.mock_instruments import DummyBase
    HAS_QCODES = True
except ImportError:
    HAS_QCODES = False

try:
    from scipy.interpolate import RegularGridInterpolator
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

from ..data_loader import MATFileLoader

logger = logging.getLogger(__name__)


class MoTe2Device(DummyBase):
    """QCoDeS instrument simulator for MoTe2 QAHE device.
    
    This simulator loads experimental data from a MATLAB file and provides
    interpolated measurements based on gate voltage settings.
    """
    
    def __init__(self, 
                 name: str,
                 data_file: str,
                 interpolation_method: str = 'linear',
                 bounds_error: bool = False,
                 fill_value: Union[str, float] = np.nan,
                 **kwargs):
        """Initialize the MoTe2 simulator.
        
        Args:
            name: Instrument name
            data_file: Path to the processed_data.mat file
            interpolation_method: Interpolation method ('linear', 'nearest', 'cubic')
            bounds_error: Whether to raise error for out-of-bounds queries
            fill_value: Fill value for out-of-bounds queries (if bounds_error=False)
            **kwargs: Additional arguments passed to Instrument
        """
        if not HAS_QCODES:
            raise ImportError("qcodes is required. Install with: pip install qcodes")
        if not HAS_SCIPY:
            raise ImportError("scipy is required. Install with: pip install scipy")
            
        super().__init__(name, **kwargs)
        
        # Load and validate data
        logger.info(f"Initializing MoTe2 device '{name}' with data file: {data_file}")
        self._loader = MATFileLoader(data_file)
        self._data = self._loader.load_data()
        
        # Store interpolation settings
        self._interpolation_method = interpolation_method
        self._bounds_error = bounds_error
        self._fill_value = fill_value
        
        # Current gate voltage values
        self._vtg_value = 0.0
        self._vbg_value = 0.0
        
        # Initialize parameters
        self._setup_parameters()
        
        # Create interpolators
        self._setup_interpolators()
        
        logger.info(f"MoTe2 device '{name}' initialized successfully")
    
    def get_idn(self) -> Dict[str, Optional[str]]:
        """Override get_idn to provide proper identification for the MoTe2 device simulator.
        
        Returns:
            Dictionary containing vendor, model, serial, and firmware information
        """
        return {
            "vendor": "MoTe2 QAHE Simulator", 
            "model": "MoTe2Device",
            "serial": self.name,
            "firmware": "1.0.0"
        }
    
    def _setup_parameters(self):
        """Setup QCoDeS parameters."""
        
        # Get voltage ranges for validation
        vtg_range, vbg_range = self._loader.get_voltage_ranges()
        
        # Settable gate voltage parameters
        self.add_parameter(
            'Vtg',
            label='Top gate voltage',
            unit='V',
            get_cmd=self._get_vtg,
            set_cmd=self._set_vtg,
            vals=qc.validators.Numbers(vtg_range[0], vtg_range[1]),
            docstring='Top gate voltage (settable)'
        )
        
        self.add_parameter(
            'Vbg', 
            label='Back gate voltage',
            unit='V',
            get_cmd=self._get_vbg,
            set_cmd=self._set_vbg,
            vals=qc.validators.Numbers(vbg_range[0], vbg_range[1]),
            docstring='Back gate voltage (settable)'
        )
        
        # Read-only lockin parameters
        self.add_parameter(
            'lockin_xx',
            label='Lock-in XX',
            unit='V',
            get_cmd=self._get_lockin_xx,
            docstring='Lock-in amplifier XX measurement (read-only)'
        )
        
        self.add_parameter(
            'lockin_xy',
            label='Lock-in XY', 
            unit='V',
            get_cmd=self._get_lockin_xy,
            docstring='Lock-in amplifier XY measurement (read-only)'
        )
        
        self.add_parameter(
            'lockin_i',
            label='Lock-in current',
            unit='A',
            get_cmd=self._get_lockin_i,
            docstring='Lock-in current measurement (read-only)'
        )
    
    def _setup_interpolators(self):
        """Create interpolators for efficient data lookup."""
        
        # Create coordinate arrays
        vtg_coords = self._data['Vtg']
        vbg_coords = self._data['Vbg']
        
        # Ensure coordinates are sorted (required for RegularGridInterpolator)
        if not np.all(np.diff(vtg_coords) > 0):
            logger.warning("Vtg coordinates are not sorted, sorting data")
            sort_idx_vtg = np.argsort(vtg_coords)
            vtg_coords = vtg_coords[sort_idx_vtg]
            # Reorder data arrays accordingly
            for key in ['lockin_xx', 'lockin_xy', 'lockin_i']:
                self._data[key] = self._data[key][:, sort_idx_vtg]
        
        if not np.all(np.diff(vbg_coords) > 0):
            logger.warning("Vbg coordinates are not sorted, sorting data")
            sort_idx_vbg = np.argsort(vbg_coords)
            vbg_coords = vbg_coords[sort_idx_vbg] 
            # Reorder data arrays accordingly
            for key in ['lockin_xx', 'lockin_xy', 'lockin_i']:
                self._data[key] = self._data[key][sort_idx_vbg, :]
        
        # Create interpolators for each lockin channel
        self._interpolators = {}
        
        for channel in ['lockin_xx', 'lockin_xy', 'lockin_i']:
            data_2d = self._data[channel]
            
            # Handle NaN values - RegularGridInterpolator doesn't handle them well
            if np.any(~np.isfinite(data_2d)):
                logger.warning(f"Found non-finite values in {channel}, replacing with nearest neighbors")
                # Simple NaN filling strategy - could be improved
                mask = np.isfinite(data_2d)
                if np.any(mask):
                    # Replace NaN with mean of finite values as fallback
                    data_2d = np.where(mask, data_2d, np.nanmean(data_2d))
                else:
                    # All values are NaN - use zeros
                    data_2d = np.zeros_like(data_2d)
            
            try:
                # Note: RegularGridInterpolator expects (vbg, vtg) order for 2D data
                interpolator = RegularGridInterpolator(
                    points=(vbg_coords, vtg_coords),
                    values=data_2d,
                    method=self._interpolation_method,
                    bounds_error=self._bounds_error,
                    fill_value=self._fill_value
                )
                
                self._interpolators[channel] = interpolator
                logger.debug(f"Created interpolator for {channel}")
                
            except Exception as e:
                logger.error(f"Failed to create interpolator for {channel}: {e}")
                # Create a dummy interpolator that returns NaN
                self._interpolators[channel] = lambda pts: np.full(pts.shape[0], np.nan)
        
        logger.info("Interpolators created successfully")
    
    def _interpolate_value(self, channel: str, vtg: float, vbg: float) -> float:
        """Interpolate a value for given gate voltages.
        
        Args:
            channel: Channel name ('lockin_xx', 'lockin_xy', 'lockin_i')
            vtg: Top gate voltage
            vbg: Back gate voltage
            
        Returns:
            Interpolated value
        """
        if channel not in self._interpolators:
            logger.error(f"No interpolator available for channel {channel}")
            return np.nan
        
        try:
            # RegularGridInterpolator expects points as (vbg, vtg)
            point = np.array([[vbg, vtg]])
            result = self._interpolators[channel](point)
            return float(result[0])
            
        except Exception as e:
            logger.error(f"Interpolation failed for {channel} at Vtg={vtg}, Vbg={vbg}: {e}")
            return np.nan
    
    # Parameter getter/setter methods
    def _get_vtg(self) -> float:
        """Get current top gate voltage."""
        return self._vtg_value
    
    def _set_vtg(self, value: float) -> None:
        """Set top gate voltage."""
        self._vtg_value = float(value)
        logger.debug(f"Set Vtg = {value} V")
    
    def _get_vbg(self) -> float:
        """Get current back gate voltage.""" 
        return self._vbg_value
    
    def _set_vbg(self, value: float) -> None:
        """Set back gate voltage."""
        self._vbg_value = float(value)
        logger.debug(f"Set Vbg = {value} V")
    
    def _get_lockin_xx(self) -> float:
        """Get interpolated lockin XX measurement."""
        return self._interpolate_value('lockin_xx', self._vtg_value, self._vbg_value)
    
    def _get_lockin_xy(self) -> float:
        """Get interpolated lockin XY measurement."""
        return self._interpolate_value('lockin_xy', self._vtg_value, self._vbg_value)
    
    def _get_lockin_i(self) -> float:
        """Get interpolated lockin current measurement."""
        return self._interpolate_value('lockin_i', self._vtg_value, self._vbg_value)
    
    # Utility methods
    def get_data_summary(self) -> Dict[str, Any]:
        """Get summary of the loaded data."""
        return self._loader.get_data_summary()
    
    def get_voltage_ranges(self):
        """Get the valid voltage ranges."""
        return self._loader.get_voltage_ranges()
    
    def set_voltages(self, vtg: float, vbg: float) -> Dict[str, float]:
        """Set both gate voltages and return all measurements.
        
        Args:
            vtg: Top gate voltage
            vbg: Back gate voltage
            
        Returns:
            Dictionary with all parameter values
        """
        self.Vtg(vtg)
        self.Vbg(vbg) 
        
        return {
            'Vtg': self.Vtg(),
            'Vbg': self.Vbg(),
            'lockin_xx': self.lockin_xx(),
            'lockin_xy': self.lockin_xy(), 
            'lockin_i': self.lockin_i()
        }
    
    def snapshot_base(self, update: bool = True, 
                     params_to_skip_update: Optional[list] = None) -> Dict[str, Any]:
        """Extended snapshot including data summary."""
        snapshot = super().snapshot_base(update, params_to_skip_update)
        
        # Add simulator-specific information
        snapshot['data_summary'] = self.get_data_summary()
        snapshot['interpolation_method'] = self._interpolation_method
        snapshot['bounds_error'] = self._bounds_error
        snapshot['fill_value'] = self._fill_value
        
        return snapshot