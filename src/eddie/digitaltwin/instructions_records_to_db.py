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
import re
from enum import StrEnum

import pandas as pd
import requests
from sqlalchemy import Column, DateTime, Integer, String, update
from sqlalchemy.engine import Connection
from sqlalchemy.schema import CheckConstraint

from eddie.digitaltwin.tables import Base, create_table

log = logging.getLogger(__name__)

# Matches one or more "<number><unit>" groups, e.g. "1y", "2w3d", "15d". Units: y = year, w = week, d = day.
_CACHE_LENGTH_PATTERN = re.compile(r"(\d{1,9})([ywd])")
_CACHE_LENGTH_FULL_PATTERN = re.compile(r"(?:\d+[ywd])+")
_CACHE_LENGTH_UNIT_TO_DAYS = {"y": 365, "w": 7, "d": 1}


def parse_cache_length(cache_length: str) -> pd.Timedelta:
    """
    Parse a 'cache_length' duration offset string (e.g. "1y", "2w3d", "15d") into a pandas Timedelta.

    Parameters
    ----------
    cache_length : str
        The duration offset string. A sequence of "<number><unit>" groups, with units
        y (365 days), w (7 days), d (1 day), e.g. "1y", "2w3d", "15d".

    Returns
    -------
    pd.Timedelta
        The parsed duration.

    Raises
    ------
    ValueError
        If 'cache_length' is not a valid duration offset string.
    """
    if not cache_length or not _CACHE_LENGTH_FULL_PATTERN.fullmatch(cache_length):
        raise ValueError(f"Invalid 'cache_length' format: '{cache_length}'. Expected e.g. '1y', '2w3d', '15d'.")
    total_days = sum(
        int(amount) * _CACHE_LENGTH_UNIT_TO_DAYS[unit] for amount, unit in _CACHE_LENGTH_PATTERN.findall(cache_length)
    )
    return pd.Timedelta(days=total_days)


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
    layer_id : str
        Identifier for the layer, interpreted by the registered 'data_provider' callable (see
        'eddie.digitaltwin.provider_registry'). For the generic 'ogc_wfs'/'arcgis_rest' providers this is a
        full endpoint URL; for 'geoapis'-based providers (e.g. in the optional 'nz_providers' module) it is a
        numeric layer ID given as a string.
    table_name : str
        Name of the table containing the data.
    unique_column_name : Optional[str]
        Name of the unique column in the table.
    fetch_mode : FetchMode
        Coverage area of the geospatial data, e.g. AOI or Full data download
    url : str
        URL pointing to the geospatial layer.
    cache_length : Optional[str]
        Optional duration offset (e.g. "1y", "2w3d", "15d") from the instructions file, configuring how long this
        layer's fetched data remains valid before it should be re-fetched.
    refresh_after : Optional[datetime]
        Expiry date computed as fetched_at + cache_length at the time of the last fetch. Only meaningful for 'full'
        fetch_mode layers: a 'full' layer is re-fetched once this date has passed. 'aoi' fetch_mode layers instead
        track expiry per logged area of interest in the 'user_log_information' table, since a single aoi layer's table
        is built up incrementally across many separate aoi fetches.
    fetched_at : Optional[datetime]
        Timestamp recording when the layer's data was last fetched.
    """  # pylint: disable=too-few-public-methods

    __tablename__ = "geospatial_layers"
    unique_id = Column(Integer, primary_key=True, autoincrement=True)
    data_provider = Column(String, nullable=False)
    layer_id = Column(String, nullable=False, comment=(
        "Provider-specific layer identifier: a numeric ID (as a string) for 'geoapis' based providers, "
        "or a full endpoint URL for the generic 'ogc_wfs'/'arcgis_rest' providers."
    ))
    table_name = Column(String, nullable=False)
    fetch_mode = Column(String, nullable=False)
    unique_column_name = Column(String, nullable=True)
    url = Column(String, nullable=False)
    cache_length = Column(String, nullable=True, comment="Duration offset, e.g. '1y', '2w3d', '15d'")
    refresh_after = Column(DateTime(timezone=True), nullable=True, comment="Expiry date for the layer's cached data")
    fetched_at = Column(DateTime(timezone=True), nullable=True, comment="When the layer's data was last fetched")

    __table_args__ = (
        CheckConstraint(
            "((unique_column_name IS NOT NULL AND fetch_mode = 'aoi') OR "
            "(unique_column_name IS NULL AND fetch_mode = 'full'))",
            name="unique_column_name_compatible_with_fetch_mode"
        ),
        # 'refresh_after' on this table only applies to 'full' fetch_mode layers. 'aoi' fetch_mode layers instead
        # have their expiry tracked per logged area of interest, on 'user_log_information.refresh_after'.
        CheckConstraint(
            "(refresh_after IS NULL OR fetch_mode = 'full')",
            name="refresh_after_only_for_full_fetch_mode"
        ),
    )


def validate_url_reachability(section: str, url: str) -> None:
    """
    Validate the URL by checking its reachability.

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
        response = requests.get(url, timeout=30)
        # Raise an exception if the response status code indicates an error
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise ValueError(f"Unreachable URL provided for {section}: '{url}'\n{e}") from e


def validate_instruction_fields(section: str, instruction: dict[str, str | int]) -> None:
    """
    Validate the fields of an instruction.
    'fetch_mode' must always be provided. 'unique_column_name' is required
    when 'fetch_mode' is AOI, and must not be provided when 'fetch_mode' is FULL.
    'cache_length' is optional and valid for both FULL and AOI fetch modes.

    Parameters
    ----------
    section : str
        The section identifier of the instruction.
    instruction : Dict[str, str | int]
        The instruction details.

    Raises
    ------
    ValueError
        - If 'fetch_mode' is missing.
        - If 'fetch_mode' is not a valid FetchMode value.
        - If 'fetch_mode' is AOI and 'unique_column_name' is missing.
        - If 'fetch_mode' is FULL and 'unique_column_name' is provided.
        - If 'cache_length' is provided but is not a valid duration offset string.
    """
    # Retrieve the values of 'fetch_mode', 'unique_column_name', and 'cache_length' from the instruction dictionary
    fetch_mode = instruction.get("fetch_mode")
    unique_column_name = instruction.get("unique_column_name")
    cache_length = instruction.get("cache_length")

    # Check fetch modes
    valid_fetch_modes = [fm.value for fm in FetchMode]
    if not fetch_mode:
        raise ValueError(f"Fetch mode is missing for {section}, must be one of {valid_fetch_modes}")
    try:
        validated_fetch_mode = FetchMode(fetch_mode.lower())
    except ValueError as e:
        raise ValueError(
            f'Invalid value for fetch_mode: "{fetch_mode}" in {section}, must be one of {valid_fetch_modes}.') from e

    # Check if both 'fetch_mode' is AOI and 'unique_column_name' is missing
    if validated_fetch_mode == FetchMode.AOI and not unique_column_name:
        raise ValueError(
            f"Fetch mode '{fetch_mode}' missing required 'unique_column_name' for {section}."
        )
    # Check if 'fetch_mode' is full and 'unique_column_name' is provided
    if validated_fetch_mode == FetchMode.FULL and unique_column_name:
        raise ValueError(
            f"Fetch mode '{fetch_mode}' incompatible with 'unique_column_name' provided for {section}."
        )
    # 'cache_length' is a duration offset (e.g. "1y", "2w3d", "15d"), valid for both FULL and AOI fetch modes.
    # For FULL layers it is used to compute a 'refresh_after' expiry date directly on the layer. For AOI layers
    # it is instead used to compute a 'refresh_after' expiry recorded against logged area of interests in the
    # 'user_log_information' table, since a single AOI layer's table is built up across many separate fetches.
    if cache_length:
        try:
            parse_cache_length(cache_length)
        except ValueError as e:
            raise ValueError(f"Invalid 'cache_length' for {section}: '{cache_length}'\n{e}") from e


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
        columns = ["section", "data_provider", "layer_id", "table_name", "fetch_mode", "unique_column_name",
                   "cache_length", "url"]
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
        # 'cache_length' is optional, so the column may not be present if no instruction specifies it
        if 'cache_length' not in instructions_df.columns:
            instructions_df['cache_length'] = None
        # Normalise missing values (NaN from the transposed dict) to None
        instructions_df['cache_length'] = instructions_df['cache_length'].where(
            instructions_df['cache_length'].notna(), None)
        # Drop duplicated records in case they exist in the 'static_boundary_instructions' file
        instructions_df = instructions_df.drop_duplicates(subset=instructions_df.columns.difference(['section']))
    return instructions_df


def get_existing_geospatial_layers(conn: Connection) -> pd.DataFrame:
    """
    Retrieve existing geospatial layers from the 'geospatial_layers' table.

    Parameters
    ----------
    conn : Connection
        The connection used to connect to the database.

    Returns
    -------
    pd.DataFrame
        Data frame containing the existing geospatial layers. Includes 'cache_length' so that records whose
        configured cache duration has changed in the instructions file can be detected and kept up to date.
    """
    # SQL query to retrieve specific columns from the geospatial_layers table
    existing_layer_query = f"""
    SELECT data_provider, layer_id, cache_length
    FROM {GeospatialLayers.__tablename__};
    """
    # Execute the query and read the results into a DataFrame
    existing_layers_df = pd.read_sql(existing_layer_query, conn)
    return existing_layers_df


def get_non_existing_records(instructions_df: pd.DataFrame, existing_layers_df: pd.DataFrame) -> pd.DataFrame:
    """
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
    merged_df = instructions_df.merge(
        existing_layers_df[['data_provider', 'layer_id']], on=['data_provider', 'layer_id'], how='left',
        indicator=True)
    # Filter for records that only exist in the instructions DataFrame (non-existing records)
    non_existing_records = merged_df[merged_df['_merge'] == 'left_only'].drop(columns='_merge')
    # Drop the 'section' column and move the 'url' column to the end
    non_existing_records = non_existing_records.drop(columns=["section"])
    non_existing_records['url'] = non_existing_records.pop('url')
    return non_existing_records


def get_updated_cache_length_records(
    instructions_df: pd.DataFrame, existing_layers_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Get records that already exist in the database but whose 'cache_length' in the instructions file has changed,
    so the stored value can be kept in sync without requiring the whole record to be removed and re-added. This
    lets an administrator change how long a layer's data is cached for (whether 'full' or 'aoi' fetch_mode) by
    updating the instructions file alone. The change only affects the 'refresh_after' expiry date computed at the
    next fetch; it does not retroactively alter the expiry of data already fetched.

    Parameters
    ----------
    instructions_df : pd.DataFrame
        Data frame containing the 'static_boundary_instructions' records.
    existing_layers_df : pd.DataFrame
        Data frame containing the existing 'static_boundary_instructions' records from the database.

    Returns
    -------
    pd.DataFrame
        Data frame of (data_provider, layer_id, cache_length) for records whose stored 'cache_length' is stale.
    """
    # Merge on the records that already exist in the database
    merged_df = instructions_df.merge(
        existing_layers_df, on=['data_provider', 'layer_id'], how='inner', suffixes=('', '_existing'))
    # A record differs if one of the two values is set and they are not equal (None != None would otherwise match)
    both_unset = merged_df['cache_length'].isna() & merged_df['cache_length_existing'].isna()
    differs = merged_df['cache_length'] != merged_df['cache_length_existing']
    changed_records = merged_df[differs & ~both_unset]
    return changed_records[['data_provider', 'layer_id', 'cache_length']]


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

    # Get existing records whose 'cache_length' has changed in the instructions file
    updated_cache_length_records = get_updated_cache_length_records(instructions_df, existing_layers_df)
    if not updated_cache_length_records.empty:
        log.info("Updating 'cache_length' for existing 'static_boundary_instructions' records in the database.")
        for _, record in updated_cache_length_records.iterrows():
            conn.execute(
                update(GeospatialLayers)
                .where(
                    GeospatialLayers.data_provider == record['data_provider'],
                    GeospatialLayers.layer_id == record['layer_id'])
                .values(cache_length=record['cache_length'])
            )
