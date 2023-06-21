# -*- coding: utf-8 -*-
"""
@Date: 14/06/2023
@Author: sli229
"""

import json
import logging
import pathlib
from typing import Dict, Union

import requests
import pandas as pd
import validators
from sqlalchemy.engine import Engine

from src.digitaltwin.tables import GeospatialLayers, create_table

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def validate_url_reachability(section: str, url: str) -> None:
    """
    Validate the URL by checking its format and reachability.

    Parameters
    ----------
    section : str
        The section identifier of the instruction.
    url : str
        The URL to validate.

    Returns
    -------
    None
        This function does not return any value.

    Raises
    ------
    ValueError
        If the URL is invalid or unreachable.
    """
    # Check if the URL is valid
    if not validators.url(url):
        raise ValueError(f"Invalid URL provided for {section}: '{url}'")
    # Check if the response status code is 200 (OK)
    response = requests.get(url)
    if response.status_code != 200:
        raise ValueError(f"Unreachable URL provided for {section}: '{url}'")


def validate_instruction_fields(section: str, instruction: Dict[str, Union[str, int]]) -> None:
    """
    Validate the fields of an instruction.
    Each instruction should provide either 'coverage_area' or 'unique_column_name', but not both.

    Parameters
    ----------
    section : str
        The section identifier of the instruction.
    instruction : Dict[str, Union[str, int]]
        The instruction details.

    Returns
    -------
    None
        This function does not return any value.

    Raises
    ------
    ValueError
        If both 'coverage_area' and 'unique_column_name' are provided or if both are not provided.
    """
    # Retrieve the values of 'coverage_area' and 'unique_column_name' from the instruction dictionary
    coverage_area = instruction.get("coverage_area")
    unique_column_name = instruction.get("unique_column_name")
    # Check if both 'coverage_area' and 'unique_column_name' are provided
    if coverage_area and unique_column_name:
        raise ValueError(
            f"Both 'coverage_area' and 'unique_column_name' provided for {section}. Only one can be provided.")
    # Check if both 'coverage_area' and 'unique_column_name' are not provided
    if not coverage_area and not unique_column_name:
        raise ValueError(
            f"Neither 'coverage_area' nor 'unique_column_name' provided for {section}. One must be provided.")


def read_and_check_instructions_file() -> pd.DataFrame:
    """
    Read and check the instructions_run file, validating URLs and instruction fields.

    Returns
    -------
    pd.DataFrame
        The processed instructions DataFrame.
    """
    # Path to the 'instructions_run.json' file
    instruction_file = pathlib.Path("src/digitaltwin/instructions_run.json")
    with open(instruction_file, "r") as file:
        instructions = json.load(file)
        for section, instruction in instructions.items():
            # Validate the URL and its reachability
            validate_url_reachability(section, instruction.get("url"))
            # Validate the instruction fields
            validate_instruction_fields(section, instruction)
        # Create the DataFrame from the instructions dictionary
        instructions_df = pd.DataFrame(instructions).transpose().reset_index(names='section')
        # Strip leading and trailing whitespace from the URLs
        instructions_df['url'] = instructions_df['url'].str.strip()
        # Drop duplicated records in case they exist in the 'instructions_run' file
        instructions_df = instructions_df.drop_duplicates(subset=instructions_df.columns.difference(['section']))
    return instructions_df


def get_existing_geospatial_layers(engine: Engine) -> pd.DataFrame:
    """
    Retrieve existing geospatial layers from the 'geospatial_layers' table.

    Parameters
    ----------
    engine : Engine
        Engine used to connect to the database.

    Returns
    -------
    pd.DataFrame
        Data frame containing the existing geospatial layers.
    """
    # SQL query to retrieve specific columns from the geospatial_layers table
    existing_layer_query = "SELECT data_provider, layer_id FROM geospatial_layers;"
    # Execute the query and read the results into a DataFrame
    existing_layers_df = pd.read_sql(existing_layer_query, engine)
    return existing_layers_df


def get_non_existing_records(instructions_df: pd.DataFrame, existing_layers_df: pd.DataFrame) -> pd.DataFrame:
    """
    Get 'instructions_run' records that are not available in the database.

    Parameters
    ----------
    instructions_df : pd.DataFrame
        Data frame containing the 'instructions_run' records.
    existing_layers_df : pd.DataFrame
        Data frame containing the existing 'instructions_run' records from the database.

    Returns
    -------
    pd.DataFrame
        Data frame containing the 'instructions_run' records that are not available in the database.
    """
    # Merge the instructions DataFrame with the existing data DataFrame
    merged_df = instructions_df.merge(existing_layers_df, on=['data_provider', 'layer_id'], how='left', indicator=True)
    # Filter for records that only exist in the instructions DataFrame (non-existing records)
    non_existing_records = merged_df[merged_df['_merge'] == 'left_only'].drop(columns='_merge')
    # Drop the 'section' column and move the 'url' column to the end
    non_existing_records = non_existing_records.drop(columns=["section"])
    non_existing_records['url'] = non_existing_records.pop('url')
    return non_existing_records


def store_instructions_records_to_db(engine: Engine) -> None:
    """
    Store 'instructions_run' records in the 'geospatial_layers' table in the database.

    Parameters
    ----------
    engine : Engine
        Engine used to connect to the database.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Create the 'geospatial_layers' table if it doesn't exist
    create_table(engine, GeospatialLayers)
    # Retrieve existing layers from the 'geospatial_layers' table
    existing_layers_df = get_existing_geospatial_layers(engine)
    # Read and check the instructions file
    instructions_df = read_and_check_instructions_file()
    # Get 'instructions_run' records that are not available in the database.
    non_existing_records = get_non_existing_records(instructions_df, existing_layers_df)

    if non_existing_records.empty:
        log.info("No new 'instructions_run' records found. All records already exist in the database.")
    else:
        # Store the non-existing records to the 'geospatial_layers' table
        non_existing_records.to_sql(GeospatialLayers.__tablename__, engine, index=False, if_exists="append")
        log.info("New 'instructions_run' records have been successfully added to the database.")
