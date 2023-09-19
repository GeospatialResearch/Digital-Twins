# -*- coding: utf-8 -*-
"""
Main tide and sea level rise script used to fetch tide data, read and store sea level rise data in the database,
and generate the requested uniform boundary model input for BG-Flood etc.
"""

import logging
import pathlib

import geopandas as gpd

from src import config
from src.digitaltwin import setup_environment
from src.digitaltwin.utils import LogLevel, setup_logging, get_catchment_area

from src.dynamic_boundary_conditions.tide_enum import ApproachType
from src.dynamic_boundary_conditions import (
    tide_query_location,
    tide_data_from_niwa,
    sea_level_rise_data,
    tide_slr_combine,
    tide_slr_model_input
)

log = logging.getLogger(__name__)


def remove_existing_boundary_inputs(bg_flood_dir: pathlib.Path) -> None:
    """
    Remove existing uniform boundary input files from the specified directory.

    Parameters
    ----------
    bg_flood_dir : pathlib.Path
        BG-Flood model directory containing the uniform boundary input files.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Iterate through all boundary files in the directory
    for boundary_file in bg_flood_dir.glob('*_bnd.txt'):
        # Remove the file
        boundary_file.unlink()


def main(selected_polygon_gdf: gpd.GeoDataFrame, log_level: LogLevel = LogLevel.DEBUG) -> None:
    try:
        # Set up logging with the specified log level
        setup_logging(log_level)
        # Connect to the database
        engine = setup_environment.get_database()
        # Get catchment area
        catchment_area = get_catchment_area(selected_polygon_gdf, to_crs=2193)
        # BG-Flood Model Directory
        bg_flood_dir = config.get_env_variable("FLOOD_MODEL_DIR", cast_to=pathlib.Path)
        # Remove any existing uniform boundary model inputs in the BG-Flood directory
        remove_existing_boundary_inputs(bg_flood_dir)

        # Get the locations used to fetch tide data
        tide_query_loc = tide_query_location.get_tide_query_locations(engine, catchment_area)
        # Fetch tide data from NIWA using the tide API
        tide_data_king = tide_data_from_niwa.get_tide_data(
            tide_query_loc=tide_query_loc,
            approach=ApproachType.KING_TIDE,
            tide_length_mins=2880,
            time_to_peak_mins=1440,
            interval_mins=10)

        # Store sea level rise data to the database
        sea_level_rise_data.store_slr_data_to_db(engine)
        # Get the closest sea level rise data from the database
        slr_data = sea_level_rise_data.get_slr_data_from_db(engine, tide_data_king)

        # Combine the tide and sea level rise (SLR) data
        tide_slr_data = tide_slr_combine.get_combined_tide_slr_data(
            tide_data=tide_data_king,
            slr_data=slr_data,
            proj_year=2030,
            confidence_level='low',
            ssp_scenario='SSP1-2.6',
            add_vlm=False,
            percentile=50)

        # Generate the uniform boundary model input
        tide_slr_model_input.generate_uniform_boundary_input(bg_flood_dir, tide_slr_data)

    except tide_query_location.NoTideDataException as error:
        # Log an info message to indicate the absence of tide data
        log.info(error)

    except RuntimeError as error:
        # Log a warning message to indicate that a runtime error occurred while fetching tide data
        log.warning(error)


if __name__ == "__main__":
    sample_polygon = gpd.GeoDataFrame.from_file("selected_polygon.geojson")
    main(sample_polygon)
