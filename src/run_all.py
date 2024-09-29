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

from enum import Enum
from types import ModuleType
from typing import Dict, Union

import geopandas as gpd
import shapely


def main(
    selected_polygon_gdf: gpd.GeoDataFrame,
    modules_to_parameters: Dict[ModuleType, Dict[str, Union[str, int, float, bool, None, Enum]]]
) -> None:
    """
    Run each module in modules_to_parameters using the selected polygon and the defined parameters for each module's
    main function.

    Parameters
    ----------
    selected_polygon_gdf : gpd.GeoDataFrame
        A GeoDataFrame representing the selected polygon, i.e., the catchment area.
    modules_to_parameters : Dict[ModuleType, Dict[str, Union[str, int, float, bool, None, Enum]]]
        A dictionary that associates each module with the parameters necessary for its main function, including the
        option to set the log level for each module's root logger.
        The available logging levels and their corresponding numeric values are:
        - LogLevel.CRITICAL (50)
        - LogLevel.ERROR (40)
        - LogLevel.WARNING (30)
        - LogLevel.INFO (20)
        - LogLevel.DEBUG (10)
        - LogLevel.NOTSET (0)
    """
    # Iterate through the dictionary containing modules and their parameters
    for module, parameters in modules_to_parameters.items():
        # Call the main function of each module with the selected polygon and specified parameters
        module.main(selected_polygon_gdf, **parameters)


def create_sample_polygon() -> gpd.GeoDataFrame:
    """
    Create a sample area of interest polygon for development purposes.
    This sample polygon is rectangular, but has non-whole number edges caused by serialisation rounding errors.
    These deliberate errors are to simulate the production system more accurarately.

    Returns
    ----------
    gpd.GeoDataFrame
        A GeoDataFrame containing a single rectangular polygon for the area of interest.
    """
    # Read the area of interest file in
    aoi = gpd.read_file("selected_taumutu.geojson")
    # Convert to WGS84 to deliberately introduce rounding errors. Ensures our development acts like production.
    # These rounding errors occur in production when serialising WGS84 polygons
    aoi = aoi.to_crs(4326)

    # Convert the polygon back to 2193 crs, and recalculate the bounds to ensure it is a rectangle.
    bbox_2193 = aoi.to_crs(2193).bounds.rename(columns={"minx": "xmin", "maxx": "xmax", "miny": "ymin", "maxy": "ymax"})
    # Create sample polygon from bounding box
    sample_polygon = gpd.GeoDataFrame(index=[0], crs="epsg:2193", geometry=[shapely.box(**bbox_2193.iloc[0])])
    return sample_polygon
