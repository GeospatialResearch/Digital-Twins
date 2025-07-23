# -*- coding: utf-8 -*-
# Copyright © 2021-2025 Geospatial Research Institute Toi Hangarau
# LICENSE: https://github.com/GeospatialResearch/Digital-Twins/blob/master/LICENSE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""This script runs each module in the Digital Twin using a Sample Polygon."""
import pathlib

from src.digitaltwin import retrieve_from_instructions
from src.digitaltwin.utils import LogLevel
from src.run_all import create_sample_polygon, main
from eddie_floodresilience.dynamic_boundary_conditions.rainfall import main_rainfall
from eddie_floodresilience.dynamic_boundary_conditions.rainfall.rainfall_enum import RainInputType, HyetoMethod
from eddie_floodresilience.dynamic_boundary_conditions.river import main_river
from eddie_floodresilience.dynamic_boundary_conditions.river.river_enum import BoundType
from eddie_floodresilience.dynamic_boundary_conditions.tide import main_tide_slr
from eddie_floodresilience.flood_model import bg_flood_model, process_hydro_dem

DEFAULT_MODULES_TO_PARAMETERS = {
    retrieve_from_instructions: {
        "log_level": LogLevel.INFO,
        "instruction_json_path": pathlib.Path("eddie_floodresilience/static_boundary_instructions.json").as_posix()
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
        "confidence_level": "medium",
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
