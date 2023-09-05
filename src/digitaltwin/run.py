# -*- coding: utf-8 -*-
"""
This script automates the retrieval and storage of geospatial data from various providers using the 'geoapis' library.
It populates the 'geospatial_layers' table in the database and stores user log information for tracking and reference.
"""
import logging

import geopandas as gpd

from src.digitaltwin import setup_environment, instructions_records_to_db, data_to_db
from src.digitaltwin.utils import LogLevel, setup_logging, get_catchment_area


def main(selected_polygon_gdf: gpd.GeoDataFrame, log_level: LogLevel = LogLevel.DEBUG) -> None:
    # Set up logging with the specified log level
    setup_logging(log_level)
    # Connect to the database
    engine = setup_environment.get_database()
    # Get catchment area
    catchment_area = get_catchment_area(selected_polygon_gdf, to_crs=2193)
    # Store 'instructions_run' records in the 'geospatial_layers' table in the database.
    instructions_records_to_db.store_instructions_records_to_db(engine)
    # Store geospatial layers data in the database
    data_to_db.store_geospatial_layers_data_to_db(engine, catchment_area)
    # Store user log information in the database
    data_to_db.user_log_info_to_db(engine, catchment_area)


if __name__ == "__main__":
    sample_polygon = gpd.GeoDataFrame.from_file("selected_polygon.geojson")
    main(sample_polygon)
