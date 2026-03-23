# -*- coding: utf-8 -*-
# Copyright © 2021-2026 Geospatial Research Institute Toi Hangarau
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

"""
This script facilitates caching model results, allowing results to be retrieved immediately if the same
scenario options are queried later.
"""
import logging

import geopandas as gpd
from sqlalchemy import insert

from eddie.digitaltwin import setup_environment
from eddie.digitaltwin.tables import CacheResults, create_table
from eddie.digitaltwin.utils import LogLevel, setup_logging

log = logging.getLogger(__name__)


def main(
    selected_polygon_gdf: gpd.GeoDataFrame,
    model_id: int,
    scenario_options: dict,
    log_level: LogLevel = LogLevel.DEBUG,
) -> int:
    """
    Cache the scenario options used to generate the existing model with the given model id, for faster retrieval later.

    Parameters
    ----------
    selected_polygon_gdf: gpd.GeoDataFrame
        The selected area of interest to cache, any area fully intersecting this one can be retrieved later if the other
        parameters match.
    model_id : int
        The database id of the existing model output to attach the cached parameters to.
    scenario_options : dict
        The input parameters to the model to cache, which must match for later retrieval.
    log_level : LogLevel = LogLevel.DEBUG
        The log level to set for the root logger. Defaults to LogLevel.DEBUG.

    Returns
    -------
    int
        model_id re-returned to allow method chaining.
    """
    # Set up logging with the specified log level
    setup_logging(log_level)
    # Connect to the database
    engine = setup_environment.get_database()
    with engine.connect() as conn:
        create_table(conn, CacheResults)
        geometry = selected_polygon_gdf.geometry[0].wkt

        # Cache the results attached to the scenario input parameters
        log.info("Caching model results.")
        query = insert(CacheResults).values(
            flood_model_id=model_id,
            geometry=geometry,
            scenario_options=scenario_options
        )
        conn.execute(query)
    # return the model_id to allow method chaining
    return model_id


if __name__ == "__main__":
    sample_polygon = gpd.GeoDataFrame.from_file("selected_polygon.geojson")
