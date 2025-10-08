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

"""
This script automates the retrieval and storage of geospatial data from various providers using the 'geoapis' library.
It populates the 'geospatial_layers' table in the database and stores user log information for tracking and reference.
"""
import pathlib

import geopandas as gpd
from sqlalchemy import insert
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import text

from src.digitaltwin import setup_environment, instructions_records_to_db, data_to_db
from src.digitaltwin.utils import LogLevel, setup_logging, get_catchment_area
from src.digitaltwin.tables import CacheResults, create_table


def main(
    selected_polygon_gdf: gpd.GeoDataFrame,
    model_id: int,
    cache_table: str,
    scenario_options: dict,
    log_level: LogLevel = LogLevel.DEBUG,
) -> None:
    """
    """
    # Set up logging with the specified log level
    setup_logging(log_level)
    # Connect to the database
    engine = setup_environment.get_database()
    create_table(engine, CacheResults)
    geometry = selected_polygon_gdf.geometry[0].wkt
    query = insert(CacheResults).values(flood_model_id=model_id, geometry=geometry, scenario_options=scenario_options)
    with engine.begin() as conn:
        conn.execute(query)
    return model_id


if __name__ == "__main__":
    sample_polygon = gpd.GeoDataFrame.from_file("selected_polygon.geojson")
