# -*- coding: utf-8 -*-
"""
Main water quality script used to fetch and store water quality data from ECAN in the database,
and retrieve it for the requested area of interest.
"""

import logging

import geopandas as gpd

from src.digitaltwin import setup_environment
from src.digitaltwin.utils import LogLevel, setup_logging, get_catchment_area
from src.environmental.water_quality import surface_water_sites, surface_water_quality

log = logging.getLogger(__name__)


def main(
        selected_polygon_gdf: gpd.GeoDataFrame,
        log_level: LogLevel = LogLevel.DEBUG) -> None:
    """
    Fetch and store water quality data from ECAN in the database, and retrieve the latest requested
    surface water quality data from the database for the specified catchment area.

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

    # Fetch surface water site data using the ArcGIS REST API and store it in the database
    surface_water_sites.store_surface_water_sites_to_db(engine)
    # Fetch surface water quality data for the requested catchment area and store it in the database
    surface_water_quality.store_surface_water_quality_to_db(engine, catchment_area)

    # Ensure surface water quality data is being served by geoserver
    surface_water_quality.serve_surface_water_quality()


if __name__ == "__main__":
    # pylint: disable=duplicate-code
    sample_polygon = gpd.GeoDataFrame.from_file("selected_polygon.geojson")
    main(
        selected_polygon_gdf=sample_polygon,
        log_level=LogLevel.DEBUG
    )
