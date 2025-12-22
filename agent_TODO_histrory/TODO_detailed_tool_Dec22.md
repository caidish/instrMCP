# TODO: detailed_tool

Plan to add a `detailed: bool = False` option to every MCP tool. Default behavior stays concise; when `detailed=True`, return current/full payload. Below, "concise" lists the fields to keep; "detailed" means existing response structure.

## QCodes tools
- [x] **qcodes_instrument_info**
  - Concise: `status/success`, `name` (or list), brief parameter summary (counts per level), omit full parameter dict/values and timing.
  - Detailed: everything now returned.
- [x] **qcodes_get_parameter_values**
  - Concise: per query `{instrument, parameter, value, error?}`; only include value
  - Detailed: everything now returned.

## General formatting rules to implement
- [x] Default `detailed=False`; when False, drop bridge_status/request_ids/debug warnings and truncate large blobs (outputs, reprs) to a short summary.
- [x] Keep return types JSON; don't change field names unless pruning for concise mode.

## Notebook (safe) tools
- **notebook_list_variables**
  - No need of concise or detailed; keep as is.
- [x] **notebook_get_variable_info**
  - Concise: `name`, `type`, `qcodes_instrument` flag, brief repr (first 10 chars).
  - Detailed: everything now returned.
- [x] **notebook_get_editing_cell**
  - Concise: `cell_type`, `cell_index`,  `cell_content`
  - Detailed: everthing now returned.
- [x] **notebook_get_editing_cell_output**
  - Concise: latest cell `outputs`,`has_output/has_error`
  - Detailed: everything now returned.
- [x] **notebook_get_notebook_cells**
  - Concise: recent cells with `cell_number`, `input` (truncated), `has_output`, `has_error`, `status`
  - Detailed: everything now returned.
- [x] **notebook_move_cursor**
  - Concise: `success`
  - Detailed: everything now returned.
- [x] **notebook_server_status**
  - no need to change; keep as is.
  - change tools_count to be dynamic_tools_count.
## Resource tools
No need to change; keep as is.

## MeasureIt tools
No need to change; keep as is.

## Database tools
- [x] **database_list_experiments**
  - Concise: experiments database_path, and only names.
  - Detailed: everything now returned.
- [x] **database_get_dataset_info**
  - Concise: `id`, `name`, `sample`, `metadata`
  - Detailed: everything now returned.
  Enhancement: has a new option: code suggestion: generate a code example how to retrieve the dataset.
  Revise the following example:
  ```
  from qcodes.dataset import load_by_id
from qcodes.dataset.sqlite.database import initialise_or_create_database_at

db = "/Users/caijiaqi/GitHub/MeasureIt/Databases/mnbi2te4_rmcd_hyst.db"
initialise_or_create_database_at(db)

ds = load_by_id(1)
d = ds.get_parameter_data()

field = d["qdb_rmcd"]["qdb_field"]
rmcd  = d["qdb_rmcd"]["qdb_rmcd"]
time  = d["time"]["time"]
```
For this tool output:
```
{
  "database_path": "/Users/caijiaqi/GitHub/MeasureIt/Databases/mnbi2te4_rmcd_hyst.db",
  "path_resolved_via": "explicit",
  "basic_info": {
    "run_id": 1,
    "captured_run_id": 1,
    "name": "results",
    "guid": "42a1fbe9-0000-0000-0000-019adbd416ce",
    "completed": true,
    "number_of_results": 1284,
    "timestamp": 1764624701.142776,
    "timestamp_readable": "2025-12-01T16:31:41.142776"
  },
  "experiment_info": {
    "experiment_id": 1,
    "name": "rmcd_hysteresis",
    "sample_name": "MnBi2Te4_device"
  },
  "parameters": {
    "qdb_field": {
      "name": "qdb_field"
    },
    "time": {
      "name": "time"
    },
    "qdb_rmcd": {
      "name": "qdb_rmcd"
    }
  },
  "metadata": {
    "measureit": "{\"class\": \"Sweep1D\", \"module\": \"measureit.sweep.sweep1d\", \"attributes\": {\"inter_delay\": 0.1, \"save_data\": true, \"plot_data\": true, \"plot_bin\": 1, \"bidirectional\": true, \"continual\": false, \"x_axis_time\": 0}, \"set_param\": {\"param\": \"field\", \"instr_module\": \"generations.devices.QDB_UKQ5TFJBH.device\", \"instr_class\": \"Device_QDB_UKQ5TFJBH\", \"instr_name\": \"qdb\", \"start\": -8.0, \"stop\": 8.0, \"step\": 0.05}, \"follow_params\": {\"qdb.rmcd\": [\"qdb\", \"generations.devices.QDB_UKQ5TFJBH.device\", \"Device_QDB_UKQ5TFJBH\"]}}"
  },
  "measureit_info": {
    "class": "Sweep1D",
    "module": "measureit.sweep.sweep1d",
    "attributes": {
      "inter_delay": 0.1,
      "save_data": true,
      "plot_data": true,
      "plot_bin": 1,
      "bidirectional": true,
      "continual": false,
      "x_axis_time": 0
    },
    "set_param": {
      "param": "field",
      "instr_module": "generations.devices.QDB_UKQ5TFJBH.device",
      "instr_class": "Device_QDB_UKQ5TFJBH",
      "instr_name": "qdb",
      "start": -8,
      "stop": 8,
      "step": 0.05
    },
    "set_params": null,
    "inner_sweep": null,
    "outer_sweep": null,
    "follow_params": {
      "qdb.rmcd": [
        "qdb",
        "generations.devices.QDB_UKQ5TFJBH.device",
        "Device_QDB_UKQ5TFJBH"
      ]
    }
  },
  "parameter_data": {
    "qdb_rmcd": {
      "qdb_rmcd": {
        "first_10": [
          -2.33984789822913,
          -2.34309384463287,
          -2.34948586830055,
          -2.34316967305923,
          -2.33841264161092,
          -2.33689180824524,
          -2.34229899908212,
          -2.33609351053232,
          -2.33506033093645,
          -2.33568497169419
        ],
        "last_10": [
          -2.32381838230558,
          -2.32128138112663,
          -2.31652526267841,
          -2.33167974471833,
          -2.33270381217669,
          -2.32356455872437,
          -2.3354456093263,
          -2.34571329187998,
          -2.34359328267948,
          -2.33984789822913
        ],
        "total_points": 642,
        "data_truncated": true
      },
      "qdb_field": {
        "first_10": [
          -8,
          -7.95,
          -7.9,
          -7.85,
          -7.8,
          -7.75,
          -7.7,
          -7.65,
          -7.6,
          -7.55
        ],
        "last_10": [
          -7.55,
          -7.6,
          -7.65,
          -7.7,
          -7.75,
          -7.8,
          -7.85,
          -7.9,
          -7.95,
          -8
        ],
        "total_points": 642,
        "data_truncated": true
      }
    },
    "time": {
      "time": {
        "first_10": [
          0.0149246668443084,
          0.120029916986823,
          0.225072707980871,
          0.325375541811809,
          0.427726541878656,
          0.529614124912769,
          0.633635957958177,
          0.738652957836166,
          0.843691874993965,
          0.948766332818195
        ],
        "last_10": [
          65.7479090418201,
          65.8530191248283,
          65.9565611248836,
          66.0567550419364,
          66.1617824579589,
          66.2653211248107,
          66.370500916848,
          66.4748304998502,
          66.5798592919018,
          66.6823940419126
        ],
        "total_points": 642,
        "data_truncated": true
      },
      "qdb_field": {
        "first_10": [
          -8,
          -7.95,
          -7.9,
          -7.85,
          -7.8,
          -7.75,
          -7.7,
          -7.65,
          -7.6,
          -7.55
        ],
        "last_10": [
          -7.55,
          -7.6,
          -7.65,
          -7.7,
          -7.75,
          -7.8,
          -7.85,
          -7.9,
          -7.95,
          -8
        ],
        "total_points": 642,
        "data_truncated": true
      }
    }
  }
}
```

- **database_get_database_stats**
  - Keep as is; no change needed.
- **database_list_available**
  - Keep as is; no change needed.

## Notebook (unsafe) tools
- [x] **notebook_update_editing_cell**
  - Concise: `success`, `message`
  - Detailed: full response incl. as now returned.
- [x] **notebook_execute_cell**
  - Concise: `signal_success`, `status`, `execution_count`, summary output, `error_type/message` if error; drop bridge_status/warning/full outputs unless error.
  - Detailed: full response incl. as now returned.
  - Bug: success should be revised to be `signal_success` to not mislead users. ✅ Fixed
- [x] **notebook_add_cell**
  - Concise: `success`
  - Detailed: full response incl. as now returned.
- [x] **notebook_delete_cell**
  - Concise: `success`
  - Detailed: full response incl. as now returned.
- [x] **notebook_delete_cells**
  - Concise: `success`
  - Detailed: full response incl. as now returned.
- [x] **notebook_apply_patch**
  - Concise: `success`
  - Detailed: full response incl. as now returned.

## Dynamic meta-tools
- [x] **dynamic_register_tool**
  - Concise: `status`, `tool_name`, `version`, `message`; drop corrected_fields unless error.
  - Detailed: full response incl. as now returned. path, full error traces.
- [x] **dynamic_update_tool**
  - Concise: `status`, `tool_name`
  - Detailed: full response incl. as now returned.
- [x] **dynamic_revoke_tool**
  - Concise: `status`
  - Detailed: full response incl. as now returned.
- [x] **dynamic_list_tools**
  - Concise: `count`, list of tool names (maybe filtered), basic fields (name, version).
  - Detailed: full response incl. as now returned.
- [x] **dynamic_inspect_tool**
  - Concise: `status`, `tool_name`
  - Detailed: full response incl. as now returned.
- [x] **dynamic_registry_stats**
  - Concise: `status`
  - Detailed: full response incl. as now returned.

## Resource: bridge/resource helper tools
Keep as is; no change needed.

