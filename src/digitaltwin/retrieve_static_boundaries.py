# -*- coding: utf-8 -*-
"""
This script automates the retrieval and storage of geospatial data from various providers using the 'geoapis' library.
It populates the 'geospatial_layers' table in the database and stores user log information for tracking and reference.
"""

import geopandas as gpd

from src.digitaltwin import setup_environment, instructions_records_to_db, data_to_db
from src.digitaltwin.utils import LogLevel, setup_logging, get_catchment_area


def main(
        selected_polygon_gdf: gpd.GeoDataFrame,
        log_level: LogLevel = LogLevel.DEBUG) -> None:
    """
    Connect to various data providers to fetch geospatial data for the selected polygon, i.e., the catchment area.
    Subsequently, populate the 'geospatial_layers' table in the database and store user log information for
    tracking and reference.

    Parameters
    ----------
    selected_polygon_gdf : gpd.GeoDataFrame
        A GeoDataFrame representing the selected polygon, i.e., the catchment area.
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
    # Connect to the database
    engine = setup_environment.get_database()
    # Get catchment area
    catchment_area = get_catchment_area(selected_polygon_gdf, to_crs=2193)
    # Store 'static_boundary_instructions' records in the 'geospatial_layers' table in the database.
    instructions_records_to_db.store_instructions_records_to_db(engine)
    # Store geospatial layers data in the database
    data_to_db.store_geospatial_layers_data_to_db(engine, catchment_area)
    # Store user log information in the database
    data_to_db.user_log_info_to_db(engine, catchment_area)
    # Read roof_surface file and store in the database
    data_to_db.save_roof_surface_data_to_db(engine)


if __name__ == "__main__":
    sample_polygon = gpd.GeoDataFrame.from_file("selected_polygon.geojson")
    main(
        selected_polygon_gdf=sample_polygon,
        log_level=LogLevel.DEBUG
    )
