"""
Sample QCodes database data for testing.

Provides mock database entries, experiments, and datasets for testing
database integration features.
"""

from typing import Dict, List, Any
from datetime import datetime, timedelta


def get_sample_experiments() -> List[Dict[str, Any]]:
    """Get sample experiment metadata."""
    base_time = datetime(2024, 1, 1, 12, 0, 0)

    return [
        {
            "exp_id": 1,
            "name": "quantum_dot_characterization",
            "sample_name": "QD_Device_A",
            "format_string": "{}-{}-{}",
            "start_time": base_time.timestamp(),
            "end_time": (base_time + timedelta(hours=2)).timestamp(),
        },
        {
            "exp_id": 2,
            "name": "gate_sweep_analysis",
            "sample_name": "QD_Device_B",
            "format_string": "{}-{}-{}",
            "start_time": (base_time + timedelta(days=1)).timestamp(),
            "end_time": (base_time + timedelta(days=1, hours=3)).timestamp(),
        },
        {
            "exp_id": 3,
            "name": "rf_spectroscopy",
            "sample_name": "Cavity_001",
            "format_string": "{}-{}-{}",
            "start_time": (base_time + timedelta(days=2)).timestamp(),
            "end_time": None,  # Still running
        },
    ]


def get_sample_datasets() -> List[Dict[str, Any]]:
    """Get sample dataset metadata."""
    base_time = datetime(2024, 1, 1, 12, 0, 0)

    return [
        {
            "run_id": 1,
            "counter": 1,
            "captured_run_id": 1,
            "captured_counter": 1,
            "experiment_id": 1,
            "name": "coulomb_diamond_scan",
            "run_timestamp": base_time.isoformat(),
            "completed_timestamp": (base_time + timedelta(minutes=30)).isoformat(),
            "records": 100,
            "metadata": {
                "temperature": 4.2,
                "gate_range": [-1, 1],
                "bias_range": [-0.5, 0.5],
                "num_points": [50, 50],
            },
            "guid": "550e8400-e29b-41d4-a716-446655440001",
        },
        {
            "run_id": 2,
            "counter": 2,
            "captured_run_id": 2,
            "captured_counter": 2,
            "experiment_id": 1,
            "name": "charge_stability_diagram",
            "run_timestamp": (base_time + timedelta(hours=1)).isoformat(),
            "completed_timestamp": (
                base_time + timedelta(hours=1, minutes=45)
            ).isoformat(),
            "records": 225,
            "metadata": {
                "temperature": 4.2,
                "plunger_gate_range": [-0.5, 0],
                "barrier_gate_range": [-1, -0.5],
                "resolution": [15, 15],
            },
            "guid": "550e8400-e29b-41d4-a716-446655440002",
        },
        {
            "run_id": 3,
            "counter": 3,
            "captured_run_id": 3,
            "captured_counter": 3,
            "experiment_id": 2,
            "name": "gate_leakage_test",
            "run_timestamp": (base_time + timedelta(days=1)).isoformat(),
            "completed_timestamp": (
                base_time + timedelta(days=1, minutes=10)
            ).isoformat(),
            "records": 20,
            "metadata": {
                "temperature": 300,
                "max_voltage": 2.0,
                "compliance_current": 1e-9,
            },
            "guid": "550e8400-e29b-41d4-a716-446655440003",
        },
        {
            "run_id": 4,
            "counter": 1,
            "captured_run_id": 4,
            "captured_counter": 1,
            "experiment_id": 3,
            "name": "cavity_transmission",
            "run_timestamp": (base_time + timedelta(days=2)).isoformat(),
            "completed_timestamp": None,  # Still running
            "records": 0,
            "metadata": {
                "frequency_range": [5e9, 7e9],
                "power": -10,
                "num_points": 1001,
            },
            "guid": "550e8400-e29b-41d4-a716-446655440004",
        },
    ]


def get_sample_parameters() -> List[Dict[str, Any]]:
    """Get sample parameter definitions for datasets."""
    return [
        {
            "name": "gate_voltage",
            "label": "Gate Voltage",
            "unit": "V",
            "paramtype": "numeric",
            "inferred_from": "",
        },
        {
            "name": "bias_voltage",
            "label": "Bias Voltage",
            "unit": "V",
            "paramtype": "numeric",
            "inferred_from": "",
        },
        {
            "name": "current",
            "label": "Current",
            "unit": "A",
            "paramtype": "numeric",
            "inferred_from": "",
        },
        {
            "name": "conductance",
            "label": "Differential Conductance",
            "unit": "S",
            "paramtype": "numeric",
            "inferred_from": "",
        },
        {
            "name": "frequency",
            "label": "Frequency",
            "unit": "Hz",
            "paramtype": "numeric",
            "inferred_from": "",
        },
        {
            "name": "s21_magnitude",
            "label": "S21 Magnitude",
            "unit": "dB",
            "paramtype": "numeric",
            "inferred_from": "",
        },
        {
            "name": "s21_phase",
            "label": "S21 Phase",
            "unit": "deg",
            "paramtype": "numeric",
            "inferred_from": "",
        },
    ]


def get_sample_database_stats() -> Dict[str, Any]:
    """Get sample database statistics."""
    return {
        "num_experiments": 3,
        "num_datasets": 4,
        "completed_datasets": 3,
        "running_datasets": 1,
        "total_records": 345,
        "oldest_run": "2024-01-01 12:00:00",
        "newest_run": "2024-01-03 12:00:00",
        "database_size_mb": 2.5,
    }


def get_sample_measurement_template() -> Dict[str, str]:
    """Get a sample measurement code template based on historical data."""
    return {
        "template_type": "2D_sweep",
        "code": """# 2D Parameter Sweep (based on run_id=1)
from qcodes.dataset import Measurement, initialise_or_create_database_at

# Initialize database
initialise_or_create_database_at('./measurements.db')

# Create measurement
meas = Measurement(name='coulomb_diamond_scan')
meas.register_parameter(gate_dac.ch01.voltage)
meas.register_parameter(bias_dac.ch01.voltage)
meas.register_parameter(dmm.current)

# Run 2D sweep
with meas.run() as datasaver:
    for gate_v in np.linspace(-1, 1, 50):
        gate_dac.ch01.voltage(gate_v)
        for bias_v in np.linspace(-0.5, 0.5, 50):
            bias_dac.ch01.voltage(bias_v)
            current = dmm.current()
            datasaver.add_result(
                (gate_dac.ch01.voltage, gate_v),
                (bias_dac.ch01.voltage, bias_v),
                (dmm.current, current)
            )
""",
        "description": "2D sweep pattern extracted from historical coulomb diamond measurements",
    }
