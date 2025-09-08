"""
Data loader for MATLAB processed data files.

Handles loading and validation of MoTe2 QAHE experimental data from .mat files.
"""

import numpy as np
from pathlib import Path
from typing import Dict, Tuple, Optional
import logging

try:
    import scipy.io
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    
logger = logging.getLogger(__name__)


class MATFileLoader:
    """Loader for MATLAB data files containing MoTe2 QAHE measurements."""
    
    def __init__(self, file_path: str):
        """Initialize the loader with a .mat file path.
        
        Args:
            file_path: Path to the processed_data.mat file
        """
        if not HAS_SCIPY:
            raise ImportError("scipy is required for loading .mat files. Install with: pip install scipy")
            
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"Data file not found: {file_path}")
            
        self._data = None
        self._is_loaded = False
        
    def load_data(self) -> Dict[str, np.ndarray]:
        """Load and validate the MATLAB data file.
        
        Returns:
            Dictionary containing the loaded data arrays
            
        Raises:
            ValueError: If data validation fails
        """
        if self._is_loaded:
            return self._data
            
        try:
            logger.info(f"Loading data from {self.file_path}")
            mat_data = scipy.io.loadmat(str(self.file_path))
            
            # Extract required arrays, removing MATLAB metadata
            required_keys = ['Vtg', 'Vbg', 'lockin_xx', 'lockin_xy', 'lockin_i']
            data = {}
            
            for key in required_keys:
                if key not in mat_data:
                    raise ValueError(f"Required key '{key}' not found in .mat file")
                    
                # Convert to numpy array and squeeze singleton dimensions
                array = np.asarray(mat_data[key]).squeeze()
                data[key] = array
                logger.debug(f"Loaded {key}: shape {array.shape}, dtype {array.dtype}")
            
            # Validate data structure
            self._validate_data_structure(data)
            
            self._data = data
            self._is_loaded = True
            logger.info("Data loaded and validated successfully")
            
            return self._data
            
        except Exception as e:
            logger.error(f"Failed to load data: {e}")
            raise
    
    def _validate_data_structure(self, data: Dict[str, np.ndarray]) -> None:
        """Validate the loaded data structure.
        
        Args:
            data: Dictionary of loaded arrays
            
        Raises:
            ValueError: If data structure is invalid
        """
        # Check Vtg and Vbg are 1D arrays
        for gate in ['Vtg', 'Vbg']:
            if data[gate].ndim != 1:
                raise ValueError(f"{gate} must be a 1D array, got shape {data[gate].shape}")
        
        n_vtg = len(data['Vtg'])
        m_vbg = len(data['Vbg'])
        
        # Check lockin arrays are 2D with correct dimensions
        for lockin in ['lockin_xx', 'lockin_xy', 'lockin_i']:
            array = data[lockin]
            if array.ndim != 2:
                raise ValueError(f"{lockin} must be a 2D array, got shape {array.shape}")
            
            # Expected shape: (m_vbg, n_vtg) for meshgrid-style indexing
            expected_shape = (m_vbg, n_vtg)
            if array.shape != expected_shape:
                raise ValueError(
                    f"{lockin} shape {array.shape} doesn't match expected {expected_shape} "
                    f"based on Vtg length {n_vtg} and Vbg length {m_vbg}"
                )
        
        # Check for NaN or inf values
        for key, array in data.items():
            if np.any(~np.isfinite(array)):
                n_bad = np.sum(~np.isfinite(array))
                logger.warning(f"Found {n_bad} non-finite values in {key}")
        
        logger.info(f"Data validation passed: Vtg({n_vtg}), Vbg({m_vbg}), lockin arrays({m_vbg}x{n_vtg})")
    
    def get_voltage_ranges(self) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        """Get the voltage ranges for Vtg and Vbg.
        
        Returns:
            Tuple of (Vtg_range, Vbg_range) where each range is (min, max)
        """
        if not self._is_loaded:
            self.load_data()
            
        vtg_range = (float(self._data['Vtg'].min()), float(self._data['Vtg'].max()))
        vbg_range = (float(self._data['Vbg'].min()), float(self._data['Vbg'].max()))
        
        return vtg_range, vbg_range
    
    def get_data_summary(self) -> Dict:
        """Get a summary of the loaded data.
        
        Returns:
            Dictionary with data summary information
        """
        if not self._is_loaded:
            self.load_data()
            
        summary = {
            'file_path': str(self.file_path),
            'vtg_points': len(self._data['Vtg']),
            'vbg_points': len(self._data['Vbg']),
            'vtg_range': (float(self._data['Vtg'].min()), float(self._data['Vtg'].max())),
            'vbg_range': (float(self._data['Vbg'].min()), float(self._data['Vbg'].max())),
            'data_shape': self._data['lockin_xx'].shape,
        }
        
        # Add statistics for each lockin channel
        for channel in ['lockin_xx', 'lockin_xy', 'lockin_i']:
            data_arr = self._data[channel]
            finite_mask = np.isfinite(data_arr)
            if np.any(finite_mask):
                summary[f'{channel}_range'] = (
                    float(data_arr[finite_mask].min()),
                    float(data_arr[finite_mask].max())
                )
            else:
                summary[f'{channel}_range'] = (np.nan, np.nan)
                
        return summary
    
    @property
    def data(self) -> Optional[Dict[str, np.ndarray]]:
        """Access to the loaded data (loads if not already loaded)."""
        if not self._is_loaded:
            self.load_data()
        return self._data
    
    @property
    def is_loaded(self) -> bool:
        """Whether data has been loaded."""
        return self._is_loaded