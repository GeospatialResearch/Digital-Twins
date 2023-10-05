# -*- coding: utf-8 -*-
"""
Main rainfall script used to fetch and store rainfall data in the database, and to generate the requested
rainfall model input for BG-Flood, etc.
"""

import pathlib

import geopandas as gpd

from src import config
from src.digitaltwin import setup_environment
from src.digitaltwin.utils import LogLevel, setup_logging, get_catchment_area, get_nz_boundary
from src.dynamic_boundary_conditions.rainfall.rainfall_enum import RainInputType, HyetoMethod
from src.dynamic_boundary_conditions.rainfall import (
    rainfall_sites,
    thiessen_polygons,
    hirds_rainfall_data_to_db,
    hirds_rainfall_data_from_db,
    hyetograph,
    rainfall_model_input,
)


def remove_existing_rain_inputs(bg_flood_dir: pathlib.Path) -> None:
    """
    Remove existing rain input files from the specified directory.

    Parameters
    ----------
    bg_flood_dir : pathlib.Path
        BG-Flood model directory containing the rain input files.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Iterate through all rain input files in the directory
    for rain_input_file in bg_flood_dir.glob('rain_forcing.*'):
        # Remove the file
        rain_input_file.unlink()


def main(selected_polygon_gdf: gpd.GeoDataFrame, log_level: LogLevel = LogLevel.DEBUG) -> None:
    """
    Generate the requested rainfall model input for BG-Flood.

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

    Returns
    -------
    None
        This function does not return any value.
    """
    # Set up logging with the specified log level
    setup_logging(log_level)
    # Connect to the database
    engine = setup_environment.get_database()
    # Get catchment area
    catchment_area = get_catchment_area(selected_polygon_gdf, to_crs=4326)

    # BG-Flood Model Directory
    bg_flood_dir = config.get_env_variable("FLOOD_MODEL_DIR", cast_to=pathlib.Path)
    # Remove any existing rainfall model inputs in the BG-Flood directory
    remove_existing_rain_inputs(bg_flood_dir)

    # Fetch rainfall sites data from the HIRDS website and store it to the database
    rainfall_sites.rainfall_sites_to_db(engine)

    # Calculate the area covered by each rainfall site across New Zealand and store it in the database
    nz_boundary = get_nz_boundary(engine, to_crs=4326)
    sites_in_nz = thiessen_polygons.get_sites_within_aoi(engine, nz_boundary)
    thiessen_polygons.thiessen_polygons_to_db(engine, nz_boundary, sites_in_nz)
    # Get coverage areas (Thiessen polygons) of rainfall sites within the catchment area
    sites_in_catchment = thiessen_polygons.thiessen_polygons_from_db(engine, catchment_area)

    # Store rainfall depth data of all the sites within the catchment area in the database
    hirds_rainfall_data_to_db.rainfall_data_to_db(engine, sites_in_catchment, idf=False)

    # Requested scenario
    rcp = 2.6
    time_period = "2031-2050"
    ari = 100
    # For a requested scenario, get all rainfall depth data for sites within the catchment area from the database
    rain_depth_in_catchment = hirds_rainfall_data_from_db.rainfall_data_from_db(
        engine, sites_in_catchment, rcp, time_period, ari, idf=False)

    # Get hyetograph data for all sites within the catchment area
    hyetograph_data = hyetograph.get_hyetograph_data(
        rain_depth_in_catchment=rain_depth_in_catchment,
        storm_length_mins=2880,
        time_to_peak_mins=1440,
        increment_mins=10,
        interp_method="cubic",
        hyeto_method=HyetoMethod.ALT_BLOCK)

    # Get the intersecting areas between the rainfall site coverage areas (Thiessen polygons) and the catchment area
    sites_coverage = rainfall_model_input.sites_coverage_in_catchment(sites_in_catchment, catchment_area)
    # Generate the requested rainfall model input for BG-Flood
    rainfall_model_input.generate_rain_model_input(
        hyetograph_data, sites_coverage, bg_flood_dir, input_type=RainInputType.UNIFORM)


if __name__ == "__main__":
    sample_polygon = gpd.GeoDataFrame.from_file("selected_polygon.geojson")
    main(
        selected_polygon_gdf=sample_polygon,
        log_level=LogLevel.DEBUG
    )
