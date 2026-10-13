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
This script processes 'static_boundary_instructions' records, validates URLs and instruction fields, and stores them in
the 'geospatial_layers' table of the database.
"""

import json
import logging
import pathlib
from enum import StrEnum
from typing import Dict, Union

import pandas as pd
import requests
from sqlalchemy import Column, Integer, String
from sqlalchemy.engine import Connection
from sqlalchemy.schema import CheckConstraint

from eddie.digitaltwin.tables import Base, create_table

log = logging.getLogger(__name__)


class FetchMode(StrEnum):
    """
    Enum for valid fetch_mode types for downloading data through instructions records.

    Attributes
    ----------
    FULL : str = "full"
        This fetch_mode will download the entire geospatial layer.
    AOI : str = "aoi"
        This fetch_mode will download only the area of interest.
    """
    FULL = "full"
    AOI = "aoi"


class GeospatialLayers(Base):
    """
    Class representing the 'geospatial_layers' table.

    Attributes
    ----------
    __tablename__ : str
        Name of the database table.
    unique_id : int
        Unique identifier for each geospatial layer entry (primary key).
    data_provider : str
        Name of the data provider.
    layer_id : int
        Identifier for the layer.
    table_name : str
        Name of the table containing the data.
    unique_column_name : Optional[str]
        Name of the unique column in the table.
    fetch_mode : FetchMode
        Coverage area of the geospatial data, e.g. AOI or Full data download
    url : str
        URL pointing to the geospatial layer.
    """  # pylint: disable=too-few-public-methods

    __tablename__ = "geospatial_layers"
    unique_id = Column(Integer, primary_key=True, autoincrement=True)
    data_provider = Column(String, nullable=False)
    layer_id = Column(Integer, nullable=False)
    table_name = Column(String, nullable=False)
    fetch_mode = Column(String, nullable=False)
    unique_column_name = Column(String, nullable=True)
    url = Column(String, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "((unique_column_name IS NOT NULL AND fetch_mode = 'aoi') OR "
            "(unique_column_name IS NULL AND fetch_mode = 'full'))",
            name="unique_column_name_compatible_with_fetch_mode"
        ),
    )


def validate_url_reachability(section: str, url: str) -> None:
    """
    Validate the URL by checking its eachability.

    Parameters
    ----------
    section : str
        The section identifier of the instruction.
    url : str
        The URL to validate.

    Raises
    ------
    ValueError
        - If the URL is unreachable.
    """
    # Check if the URL is reachable
    try:
        # Send a GET request to the URL
        response = requests.get(url)
        # Raise an exception if the response status code indicates an error
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise ValueError(f"Unreachable URL provided for {section}: '{url}'\n{e}") from e


def validate_instruction_fields(section: str, instruction: Dict[str, Union[str, int]]) -> None:
    """
    Validate the fields of an instruction.
    'fetch_mode' must always be provided. 'unique_column_name' is required
    when 'fetch_mode' is AOI, and must not be provided when 'fetch_mode' is FULL.

    Parameters
    ----------
    section : str
        The section identifier of the instruction.
    instruction : Dict[str, Union[str, int]]
        The instruction details.

    Raises
    ------
    ValueError
        - If 'fetch_mode' is missing.
        - If 'fetch_mode' is not a valid FetchMode value.
        - If 'fetch_mode' is AOI and 'unique_column_name' is missing.
        - If 'fetch_mode' is FULL and 'unique_column_name' is provided.
    """
    # Retrieve the values of 'fetch_mode' and 'unique_column_name' from the instruction dictionary
    fetch_mode = instruction.get("fetch_mode")
    unique_column_name = instruction.get("unique_column_name")

    # Check fetch modes
    valid_fetch_modes = [fm.value for fm in FetchMode]
    if not fetch_mode:
        raise ValueError(f"Fetch mode is missing for {section}, must be one of {valid_fetch_modes}")
    if fetch_mode.lower() not in valid_fetch_modes:
        raise ValueError(
            f'Invalid value for fetch_mode: "{fetch_mode}" in {section}.'
        )

    # Check if both 'fetch_mode' is AOI and 'unique_column_name' is missing
    if fetch_mode == FetchMode.AOI and not unique_column_name:
        raise ValueError(
            f"Fetch mode '{fetch_mode}' missing required 'unique_column_name' for {section}."
        )
    # Check if 'fetch_mode' is full and 'unique_column_name' is provided
    if fetch_mode == FetchMode.FULL and unique_column_name:
        raise ValueError(
            f"Fetch mode '{fetch_mode}' incompatible with 'unique_column_name' provided for {section}."
        )


def read_and_check_instructions_file(instruction_json_path: pathlib.Path | None) -> pd.DataFrame:
    """
    Read and check an instructions json file, validating URLs and instruction fields.

    Parameters
    -------
    instruction_json_path: pathlib.Path | None
        Path to the instruction json file. If this is None, then returns an empty DataFrame with the correct columns.
    Returns
    -------
    pd.DataFrame
        The processed instructions DataFrame.
    """
    if instruction_json_path is None or not instruction_json_path.is_file():
        # If the file does not exist, return a dataframe of the correct shape with no rows.
        columns = ["section", "data_provider", "layer_id", "table_name", "fetch_mode", "unique_column_name", "url"]
        return pd.DataFrame({col_name: pd.Series(dtype='object') for col_name in columns})

    # Read the instructions json file
    with open(instruction_json_path, "r", encoding="utf-8") as file:
        # Load content from the file
        instructions = json.load(file)
        # Iterate through each section
        for section, instruction in instructions.items():
            # Validate the URL and its reachability
            validate_url_reachability(section, instruction.get("url"))
            # Validate the instruction fields
            validate_instruction_fields(section, instruction)
        # Create the DataFrame from the instructions dictionary
        instructions_df = pd.DataFrame(instructions).transpose().reset_index(names='section')
        # Strip leading and trailing whitespace from the URLs
        instructions_df['url'] = instructions_df['url'].str.strip()
        # Drop duplicated records in case they exist in the 'static_boundary_instructions' file
        instructions_df = instructions_df.drop_duplicates(subset=instructions_df.columns.difference(['section']))
    return instructions_df


def get_existing_geospatial_layers(conn: Connection) -> pd.DataFrame:
    """ # todo this needs a cache check
    Retrieve existing geospatial layers from the 'geospatial_layers' table.

    Parameters
    ----------
    conn : Connection
        The connection used to connect to the database.

    Returns
    -------
    pd.DataFrame
        Data frame containing the existing geospatial layers.
    """
    # SQL query to retrieve specific columns from the geospatial_layers table
    existing_layer_query = f"""
    SELECT data_provider, layer_id
    FROM {GeospatialLayers.__tablename__};
    """
    # Execute the query and read the results into a DataFrame
    existing_layers_df = pd.read_sql(existing_layer_query, conn)
    return existing_layers_df


def get_non_existing_records(instructions_df: pd.DataFrame, existing_layers_df: pd.DataFrame) -> pd.DataFrame:
    """ # todo this needs a cache expiry time check -- ACTUALLY maybe its only needed before now
    Get 'static_boundary_instructions' records that are not available in the database.

    Parameters
    ----------
    instructions_df : pd.DataFrame
        Data frame containing the 'static_boundary_instructions' records.
    existing_layers_df : pd.DataFrame
        Data frame containing the existing 'static_boundary_instructions' records from the database.

    Returns
    -------
    pd.DataFrame
        Data frame containing the 'static_boundary_instructions' records that are not available in the database.
    """
    # Merge the instructions DataFrame with the existing data DataFrame
    merged_df = instructions_df.merge(existing_layers_df, on=['data_provider', 'layer_id'], how='left', indicator=True)
    # Filter for records that only exist in the instructions DataFrame (non-existing records)
    non_existing_records = merged_df[merged_df['_merge'] == 'left_only'].drop(columns='_merge')
    # Drop the 'section' column and move the 'url' column to the end
    non_existing_records = non_existing_records.drop(columns=["section"])
    non_existing_records['url'] = non_existing_records.pop('url')
    return non_existing_records


def store_instructions_records_to_db(conn: Connection, instruction_json_path: pathlib.Path | None) -> None:
    """
    Store instruction json file records in the 'geospatial_layers' table in the database.

    Parameters
    ----------
    conn : Connection
        The connection used to connect to the database.
    instruction_json_path : pathlib.Path | None
        The path to the instruction json file to store records for.
        If this is None, no records are stored but the tables are initialized.
    """
    # Create the 'geospatial_layers' table if it doesn't exist
    create_table(conn, GeospatialLayers)
    # Retrieve existing layers from the 'geospatial_layers' table
    existing_layers_df = get_existing_geospatial_layers(conn)
    # Read and check the instructions file
    instructions_df = read_and_check_instructions_file(instruction_json_path)
    # Get 'static_boundary_instructions' records that are not available in the database.
    non_existing_records = get_non_existing_records(instructions_df, existing_layers_df)

    if non_existing_records.empty:
        log.info("No new 'static_boundary_instructions' records found. All records already exist in the database.")
    else:
        # Store the non-existing records to the 'geospatial_layers' table
        log.info("Adding new 'static_boundary_instructions' records to the database.")
        non_existing_records.to_sql(GeospatialLayers.__tablename__, conn, index=False, if_exists="append")
