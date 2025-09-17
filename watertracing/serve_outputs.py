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

import pathlib

import geopandas as gpd

from src.digitaltwin.utils import LogLevel, setup_logging
import src.geoserver as gs


def upload_water_tracing_rgb_model_output(rgb_model_output_path: pathlib.Path) -> None:
    """
    Uploads an RGB water tracing model output GeoTiff to geoserver with appropriate band names.

    Parameters
    ----------
    rgb_model_output_path : pathlib.Path
        The path to the RGB water tracing model output GeoTiff file to upload.
    """
    # Define band names, units and formats.
    coverage_dimensions = [gs.CoverageDimension(band_name, "", "UNSIGNED_8BITS") for band_name in
                           ("Streams", "Rain", "Tide")]
    # Upload the raster file.
    workspace_name = gs.Workspaces.MODEL_OUTPUTS_WORKSPACE
    gs.create_workspace_if_not_exists(workspace_name)
    gs.add_gtiff_to_geoserver(rgb_model_output_path, workspace_name, rgb_model_output_path.stem, coverage_dimensions)
    gs.add_style(rgb_model_output_path.with_suffix(".sld"), replace=True)


def main(
    _selected_polygon_gdf: gpd.GeoDataFrame | None,
    rgb_model_output_path: pathlib.Path,
    log_level: LogLevel = LogLevel.DEBUG,
) -> None:
    """
    Uploads model output data to geoserver.
    Main function called when using this script as part of the EDDIE framework.

    Parameters
    ----------
    _selected_polygon_gdf : gpd.GeoDataFrame | None
        A GeoDataFrame representing the selected polygon. Unused in this EDDIE module.
    rgb_model_output_path : pathlib.Path
        The path to the RGB water tracing model output file to upload.
    log_level : LogLevel = LogLevel.DEBUG
        The log level to set for the root logger. Defaults to LogLevel.DEBUG.
        The available logging levels and their corresponding numeric values are:
        - LogLevel.CRITICAL (50)
        - LogLevel.ERROR (40)
        - LogLevel.WARNING (30)
        - LogLevel.INFO (20)
        - LogLevel.DEBUG (10)
        - LogLevel.NOTSET (0)
    """
    # Set up logging with the specified log level
    setup_logging(log_level)
    upload_water_tracing_rgb_model_output(rgb_model_output_path)


if __name__ == '__main__':
    sample_polygon = None
    main(None, pathlib.Path("watertracing/static/watersourceRGB_8bit_1m.tif"))
