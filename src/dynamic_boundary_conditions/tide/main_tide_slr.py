# -*- coding: utf-8 -*-
"""
Main tide and sea level rise script used to fetch tide data, download and store sea level rise data in the database,
and generate the requested tide uniform boundary model input for BG-Flood etc.
"""

import logging
import pathlib
from typing import Dict, NamedTuple, Union, Optional

import geopandas as gpd
import pandas as pd
from sqlalchemy import engine, text

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


class ValidationResult(NamedTuple):
    """
    Represents the result of checking validation on parameters.

    Attributes
    ----------
    is_valid : bool
        If True then the parameters are valid, if False then they are invalid.
    invalid_reason : Optional[str]
        An error message describing the reason the validation has failed. Can be `None` if `is_valid is True`.
    """
    is_valid: bool
    invalid_reason: Optional[str]


def validate_slr_parameters(
    engine: engine.Engine,
    proj_year: int,
    confidence_level: str,
    ssp_scenario: str,
    add_vlm: bool,
    percentile: int,
    increment_year: int = 1
) -> ValidationResult:
    """
    Validate each of the sea-level-rise parameters have valid values by querying the database.
    Returns a ValidationResult so that you can easily check for validation and the reason for failure.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
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
    increment_year : int = 1

    Returns
    -------
    ValidationResult
        Result of the validation, with validation failure reason if applicable.
    """
    valid_parameters = get_valid_parameters_based_on_confidence_level()

    # Check if the provided confidence level is valid
    if confidence_level not in valid_parameters:
        return ValidationResult(False,
                                f"Invalid value '{confidence_level}' for confidence_level. "
                                f"Must be one of {list(valid_parameters.keys())}.")

    # Check if the provided SSP scenario is valid
    valid_ssp_scenarios = valid_parameters[confidence_level]['ssp_scenarios']
    if ssp_scenario not in valid_ssp_scenarios:
        return ValidationResult(False,
                                f"Invalid value '{ssp_scenario}' for ssp_scenario."
                                f" Must be one of {valid_ssp_scenarios}.")

    # Check if the provided add_vlm value is valid
    valid_add_vlms = [True, False]
    if add_vlm not in valid_add_vlms:
        return ValidationResult(False,
                                f"Invalid value '{add_vlm}' for add_vlm. Must be one of {valid_add_vlms}.")

    # Get the percentiles from the column names and check if the provided percentile value is valid
    column_names_query = text(r"""
        SELECT column_name
        FROM information_schema.columns
        WHERE
            table_name = 'sea_level_rise'
            AND table_catalog=:db_name
            AND column_name ~ '^p\d+'
        """).bindparams(db_name=config.get_env_variable("POSTGRES_DB"))
    percentile_col_tuples = engine.execute(column_names_query).fetchall()
    # Flatten the result of the query
    percentile_cols = [col_tuple[0] for col_tuple in percentile_col_tuples]
    # Remove the leading 'p'
    valid_percentiles = [int(col[1:]) for col in percentile_cols]

    if percentile not in valid_percentiles:
        return ValidationResult(
            False,
            f"Invalid value '{percentile}' for percentile. Must be one of {valid_percentiles}.")

    # Check if the provided projection year is valid
    min_year = valid_parameters[confidence_level]['min_year']
    max_year = valid_parameters[confidence_level]['max_year']
    valid_proj_year = range(min_year, max_year + increment_year, increment_year)
    if proj_year not in valid_proj_year:
        return ValidationResult(
            False,
            f"Invalid value '{proj_year}' for proj_year. Must be one of {list(valid_proj_year)}.")

    # Pass the validation
    return ValidationResult(True, None)


def get_valid_parameters_based_on_confidence_level() -> Dict[str, Union[str, int]]:
    """
    Get information on valid tide and sea-level-rise parameters based on the valid values in the database.
    These parameters are mostly dependent on the "confidence_level" parameter, so that is the key in the returned dict.

    Returns
    -------
    Dict[str, Union[str, int]]
        Dictionary with confidence_level as the key, and the allowed values for other items as values.
    """
    # Connect to database
    engine = setup_environment.get_database()
    # Find all distinct combinations of confidence_level with the dependant columns.
    query = text(f"""
        SELECT DISTINCT
            confidence_level,
            CONCAT(ssp, '-', scenario) AS ssp_scenarios,
            (DATE_PART('year', now()) + 1)::NUMERIC::BIGINT AS min_year,
            MAX(year) AS max_year
        FROM {slr_table_name}
        GROUP BY
            confidence_level,
            ssp,
            scenario
    """)
    query_result = pd.read_sql(query, engine)

    # Construct result dict pairing confidence level to dependant variables.
    confidence_level_to_valid_params = {}
    for confidence_level, group in query_result.groupby(['confidence_level']):
        # Create nested dict of valid parameter values for each confidence level value
        valid_params = {}
        for column in group:
            # We already have confidence_level at the highest level in the dict
            if column != 'confidence_level':
                # List all different unique values for the column and given confidence level
                unique_values = group[column].unique().tolist()
                # Get the first value if it is a single value list (e.g. max_year)
                unique_values = unique_values[0] if len(unique_values) == 1 else unique_values
                valid_params[column] = unique_values
        confidence_level_to_valid_params[confidence_level] = valid_params
    return confidence_level_to_valid_params


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
    log_level: LogLevel = LogLevel.DEBUG
) -> None:
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

        # Store sea level rise data to the database
        sea_level_rise_data.store_slr_data_to_db(engine)

        # Validate input parameters
        increment_year = 1
        is_valid, invalid_reason = validate_slr_parameters(
            engine,
            proj_year,
            confidence_level,
            ssp_scenario,
            add_vlm,
            percentile,
            increment_year,
        )

        if not is_valid:
            raise ValueError(invalid_reason)

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
            percentile=percentile,
            increment_year=increment_year
        )

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
