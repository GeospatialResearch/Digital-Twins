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

"""This script runs each module in the Porirua Explorer using a Sample Polygon."""
import pathlib

from src.digitaltwin import retrieve_from_instructions
from src.digitaltwin.utils import LogLevel
from src.run_all import create_sample_polygon, main

from watertracing import serve_outputs

DEFAULT_MODULES_TO_PARAMETERS = {
    retrieve_from_instructions: {
        "log_level": LogLevel.INFO,
        "instruction_json_path": None
    },
    serve_outputs: {
        "log_level": LogLevel.INFO,
        "rgb_model_output_path": pathlib.Path("watertracing/static/watersourceRGB_8bit_1m.tif"),
    }
}

if __name__ == '__main__':
    sample_polygon = create_sample_polygon()

    # Run all modules with sample polygon that intentionally contains slight rounding errors.
    main(sample_polygon, DEFAULT_MODULES_TO_PARAMETERS)
