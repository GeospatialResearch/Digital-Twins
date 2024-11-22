# -*- coding: utf-8 -*-
"""This script runs each module in the Digital Twin using a Sample Polygon."""
import pathlib

from src.digitaltwin import retrieve_from_instructions
from src.digitaltwin.utils import LogLevel
from src.run_all import create_sample_polygon, main
from floodresilience.dynamic_boundary_conditions.rainfall import main_rainfall
from floodresilience.dynamic_boundary_conditions.rainfall.rainfall_enum import RainInputType, HyetoMethod
from floodresilience.dynamic_boundary_conditions.river import main_river
from floodresilience.dynamic_boundary_conditions.river.river_enum import BoundType
from floodresilience.dynamic_boundary_conditions.tide import main_tide_slr
from floodresilience.flood_model import bg_flood_model, process_hydro_dem

DEFAULT_MODULES_TO_PARAMETERS = {
    retrieve_from_instructions: {
        "log_level": LogLevel.INFO,
        "instruction_json_path": pathlib.Path("floodresilience/static_boundary_instructions.json")
    },
    process_hydro_dem: {
        "log_level": LogLevel.INFO
    },
    main_rainfall: {
        "rcp": 2.6,
        "time_period": "2031-2050",
        "ari": 100,
        "storm_length_mins": 2880,
        "time_to_peak_mins": 1440,
        "increment_mins": 10,
        "hyeto_method": HyetoMethod.ALT_BLOCK,
        "input_type": RainInputType.UNIFORM,
        "log_level": LogLevel.INFO
    },
    main_tide_slr: {
        "tide_length_mins": 2880,
        "time_to_peak_mins": 1440,
        "interval_mins": 10,
        "proj_year": 2030,
        "confidence_level": "low",
        "ssp_scenario": "SSP1-2.6",
        "add_vlm": False,
        "percentile": 50,
        "log_level": LogLevel.INFO
    },
    main_river: {
        "flow_length_mins": 2880,
        "time_to_peak_mins": 1440,
        "maf": True,
        "ari": None,
        "bound": BoundType.MIDDLE,
        "log_level": LogLevel.INFO
    },
    bg_flood_model: {
        "output_timestep": 1,
        "end_time": 2,
        "resolution": None,
        "mask": 9999,
        "gpu_device": -1,
        "small_nc": 0,
        "log_level": LogLevel.INFO
    }
}

if __name__ == '__main__':
    sample_polygon = create_sample_polygon()

    # Run all modules with sample polygon that intentionally contains slight rounding errors.
    main(sample_polygon, DEFAULT_MODULES_TO_PARAMETERS)
