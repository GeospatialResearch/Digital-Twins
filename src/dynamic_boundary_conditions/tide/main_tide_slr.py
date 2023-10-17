# -*- coding: utf-8 -*-
"""
Main tide and sea level rise script used to fetch tide data, read and store sea level rise data in the database,
and generate the requested tide uniform boundary model input for BG-Flood etc.
"""

import logging
import pathlib
from typing import Union

import geopandas as gpd

from src import config
from src.digitaltwin import setup_environment
from src.digitaltwin.utils import LogLevel, setup_logging, get_catchment_area

from src.dynamic_boundary_conditions.tide.tide_enum import ApproachType
from src.dynamic_boundary_conditions.tide import (
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


def get_or_load_tide_data_for_demo(
        tide_query_loc: gpd.GeoDataFrame,
        tide_length_mins: int,
        time_to_peak_mins: Union[int, float],
        interval_mins: int):
    """
    Retrieve or load tide data for demonstration.

    Parameters
    ----------
    tide_query_loc : gpd.GeoDataFrame
        A GeoDataFrame containing the locations used to fetch tide data from NIWA using the tide API.
    tide_length_mins : int
        The length of the tide event in minutes.
    time_to_peak_mins : Union[int, float]
        The time in minutes when the tide is at its greatest (reaches maximum).
    interval_mins : int
        The time interval, in minutes, between each recorded tide data point.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the retrieved or loaded tide data for demonstration.
    """
    try:
        # Fetch tide data from NIWA using the tide API
        tide_data_king = tide_data_from_niwa.get_tide_data(
            tide_query_loc=tide_query_loc,
            approach=ApproachType.KING_TIDE,
            tide_length_mins=tide_length_mins,
            time_to_peak_mins=time_to_peak_mins,
            interval_mins=interval_mins)
    except RuntimeError:
        # Load the preprocessed tide data for DEMO
        data_dir = config.get_env_variable("DATA_DIR", cast_to=pathlib.Path)
        tide_data_king_path = data_dir / "tide_data_king.geojson"
        tide_data_king = gpd.read_file(tide_data_king_path)
    return tide_data_king


def main(
        selected_polygon_gdf: gpd.GeoDataFrame,
        tide_length_mins: int,
        time_to_peak_mins: Union[int, float],
        interval_mins: int,
        proj_year: int,
        confidence_level: str,
        ssp_scenario: str,
        add_vlm: bool,
        percentile: int,
        log_level: LogLevel = LogLevel.DEBUG) -> None:
    """
    Fetch tide data, read and store sea level rise data in the database, and generate the requested tide
    uniform boundary model input for BG-Flood.

    Parameters
    ----------
    selected_polygon_gdf : gpd.GeoDataFrame
        A GeoDataFrame representing the selected polygon, i.e., the catchment area.
    tide_length_mins : int
        The length of the tide event in minutes.
    time_to_peak_mins : Union[int, float]
        The time in minutes when the tide is at its greatest (reaches maximum).
    interval_mins : int
        The time interval, in minutes, between each recorded tide data point.
    proj_year : int
        The projection year for which the combined tide and sea level rise data should be generated.
    confidence_level : str
        The desired confidence level for the sea level rise data. Valid values are 'low' or 'medium'.
    ssp_scenario : str
        The desired Shared Socioeconomic Pathways (SSP) scenario for the sea level rise data.
        Valid options for both low and medium confidence are: 'SSP1-2.6', 'SSP2-4.5', or 'SSP5-8.5'.
        Additional options for medium confidence are: 'SSP1-1.9' or 'SSP3-7.0'.
    add_vlm : bool
        Indicates whether Vertical Land Motion (VLM) should be included in the sea level rise data.
        Set to True if VLM should be included, False otherwise.
    percentile : int
        The desired percentile for the sea level rise data. Valid values are 17, 50, or 83.
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
            tide_length_mins=tide_length_mins,
            time_to_peak_mins=time_to_peak_mins,
            interval_mins=interval_mins)

        # Fetch or load tide data for demonstration
        # tide_data_king = get_or_load_tide_data_for_demo(
        #     tide_query_loc, tide_length_mins, time_to_peak_mins, interval_mins)

        # Store sea level rise data to the database
        sea_level_rise_data.store_slr_data_to_db(engine)
        # Get the closest sea level rise data from the database
        slr_data = sea_level_rise_data.get_slr_data_from_db(engine, tide_data_king)

        # Combine the tide and sea level rise (SLR) data
        tide_slr_data = tide_slr_combine.get_combined_tide_slr_data(
            tide_data=tide_data_king,
            slr_data=slr_data,
            proj_year=proj_year,
            confidence_level=confidence_level,
            ssp_scenario=ssp_scenario,
            add_vlm=add_vlm,
            percentile=percentile)

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
    main(
        selected_polygon_gdf=sample_polygon,
        tide_length_mins=2880,
        time_to_peak_mins=1440,
        interval_mins=10,
        proj_year=2030,
        confidence_level="low",
        ssp_scenario="SSP1-2.6",
        add_vlm=False,
        percentile=50,
        log_level=LogLevel.DEBUG
    )
