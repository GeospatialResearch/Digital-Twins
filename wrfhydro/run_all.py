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
from wrfhydro.forcing_data import read_forcing_data
from wrfhydro.land_surface_model import create_land_surface_model
from wrfhydro.scenario import run_wrf_hydro_scenario

DEFAULT_MODULES_TO_PARAMETERS = {
    retrieve_from_instructions: {
        "log_level": LogLevel.INFO,
        "instruction_json_path": pathlib.Path("wrfhydro/static_boundary_instructions.json").as_posix()
    },
    create_land_surface_model: {
        "log_level": LogLevel.INFO,
    },
    read_forcing_data: {
        "log_level": LogLevel.INFO,
    },
    run_wrf_hydro_scenario: {
        "log_level": LogLevel.INFO,
    },
}

if __name__ == '__main__':
    sample_polygon = create_sample_polygon()

    # Run all modules with sample polygon that intentionally contains slight rounding errors.
    main(sample_polygon, DEFAULT_MODULES_TO_PARAMETERS)
