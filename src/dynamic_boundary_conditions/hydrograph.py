# -*- coding: utf-8 -*-
"""
@Description: This script obtains river flow scenario data, whether Mean Annual Flood (MAF) or Average Recurrence
              Interval (ARI)-based, and generates corresponding hydrograph data for the requested scenarios.
@Author: sli229
"""

import logging
from typing import List, Union, Optional
import re

import geopandas as gpd

from src.dynamic_boundary_conditions.river_enum import BoundType

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def clean_river_flow_data(matched_data: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Selects and cleans specific columns representing river flow data from the given GeoDataFrame.

    Parameters
    ----------
    matched_data : gpd.GeoDataFrame
        A GeoDataFrame containing the matched data between REC1 rivers and OSM waterways,
        along with the identified target locations used for the river input in the BG-Flood model.

    Returns
    -------
    gpd.GeoDataFrame
        A new GeoDataFrame containing the selected columns representing river flow data.
    """
    # Copy input GeoDataFrame to preserve original data
    river_flow_data = matched_data.copy()
    # Select columns starting with 'h' and include 'areakm2', 'target_point' and 'dem_resolution'
    river_flow_data = river_flow_data.filter(regex=r'^h|^areakm2$|^target_point$|^dem_resolution$')
    # Define a mapping of old column names to new column names for renaming
    column_mapping = {
        r'^h_c18_': 'flow_',
        r'^hcse_': 'flow_se_',
        r'_yr$|y$': '',
    }
    # Rename columns using the column_mapping dictionary and regex matching
    river_flow_data.columns = river_flow_data.columns.to_series().replace(column_mapping, regex=True)
    # Move the 'areakm2' column to the last column
    river_flow_data['areakm2'] = river_flow_data.pop('areakm2')
    return river_flow_data


def extract_valid_ari_values(river_flow_data: gpd.GeoDataFrame) -> List[int]:
    """
    Extracts valid ARI (Annual Recurrence Interval) values from the column names of the river flow data.

    Parameters
    ----------
    river_flow_data : gpd.GeoDataFrame
        A GeoDataFrame containing river flow data with column names that include ARI values.

    Returns
    -------
    List[int]
        A list of valid ARI values extracted from the column names of the river flow data.
    """
    # Define the regex pattern to extract ARI values from column names
    ari_pattern = re.compile(r'flow_(\d+)')
    # Get the column names of the river flow data
    column_names = river_flow_data.columns
    # Extract valid ARI values from column names using the regex pattern
    valid_ari_values = [int(match.group(1)) for col_name in column_names if (match := ari_pattern.search(col_name))]
    # Sort and return the list of valid ARI values
    return sorted(valid_ari_values)


def get_river_flow_scenario_data(
        matched_data: gpd.GeoDataFrame,
        maf: bool = True,
        ari: Optional[int] = None,
        bound: BoundType = BoundType.MIDDLE) -> gpd.GeoDataFrame:
    """
    Obtain the requested river flow scenario data, which can be either Mean Annual Flood (MAF)-based or
    Average Recurrence Interval (ARI)-based scenario data.

    Parameters
    ----------
    matched_data : gpd.GeoDataFrame
        A GeoDataFrame containing the matched data between REC1 rivers and OSM waterways,
        along with the identified target locations used for the river input in the BG-Flood model.
    maf : bool, optional
        Set to True to obtain MAF-based scenario data or False to obtain ARI-based scenario data.
    ari : int, optional
        The Average Recurrence Interval (ARI) value. Valid options are 5, 10, 20, 50, 100, or 1000.
        Mandatory when 'maf' is set to False, and should be set to None when 'maf' is set to True.
    bound : BoundType, optional
        Set the type of bound (estimate) for the river flow scenario data.
        Valid options include: BoundType.LOWER, BoundType.MIDDLE, or BoundType.UPPER.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the requested river flow scenario data.

    Raises
    ------
    ValueError
        - If 'ari' is provided when 'maf' is set to True (i.e. 'maf' is True and 'ari' is not set to None).
        - If 'ari' is not provided when 'maf' is set to False (i.e. 'maf' is False and 'ari' is set to None).
        - If an invalid 'ari' value is provided.
    """
    # Selects and cleans the river flow data
    river_flow_data = clean_river_flow_data(matched_data)
    if maf:
        # If MAF-based scenario is selected, ensure 'ari' is not provided (set to None)
        if ari is not None:
            raise ValueError("When 'maf' is set to True, 'ari' should be set to None (i.e. should not be provided).")
        # Extract MAF-based scenario and rename relevant columns for clarity
        sel_data = river_flow_data[
            ['target_point', 'dem_resolution', 'areakm2', 'flow_maf', 'flow_se_maf']]
        sel_data = sel_data.rename(columns={'flow_maf': 'maf', 'flow_se_maf': 'flow_se'})
        sel_data['middle'] = sel_data['maf']
    else:
        # If ARI-based scenario is selected, ensure 'ari' is provided (not set to None)
        if ari is None:
            raise ValueError("When 'maf' is set to False, 'ari' should not be set to None (i.e. should be provided).")
        # Check for valid ARI values
        valid_ari_values = extract_valid_ari_values(river_flow_data)
        if ari not in valid_ari_values:
            raise ValueError(f"Invalid 'ari' value: {ari}. Must be one of {valid_ari_values}.")
        # Extract ARI-based scenario and rename relevant columns for clarity
        sel_data = river_flow_data[
            ['target_point', 'dem_resolution', 'areakm2', 'flow_maf', f'flow_se_{ari}', f'flow_{ari}']]
        sel_data = sel_data.rename(columns={'flow_maf': 'maf', f'flow_se_{ari}': 'flow_se', f'flow_{ari}': 'middle'})
    # Calculate lower and upper bounds for the scenario
    sel_data['lower'] = sel_data['middle'] - sel_data['flow_se']
    sel_data['upper'] = sel_data['middle'] + sel_data['flow_se']
    # Remove unnecessary column and reset the index
    sel_data = sel_data.drop(columns=['flow_se']).reset_index(drop=True)
    # Assign a unique identifier (target_point_no) starting from 1 to each target_point
    sel_data.insert(0, 'target_point_no', sel_data.index + 1)
    # Select columns to retain only relevant information
    sel_data = sel_data[['target_point_no', 'target_point', 'dem_resolution', 'areakm2', 'maf', f'{bound.value}']]
    return sel_data


def get_hydrograph_data(
        matched_data: gpd.GeoDataFrame,
        flow_length_mins: int,
        time_to_peak_mins: Union[int, float],
        maf: bool = True,
        ari: Optional[int] = None,
        bound: BoundType = BoundType.MIDDLE) -> gpd.GeoDataFrame:
    """
    Generate hydrograph data for the requested river flow scenario.

    Parameters
    ----------
    matched_data : gpd.GeoDataFrame
        A GeoDataFrame containing the matched data between REC1 rivers and OSM waterways,
        along with the identified target locations used for the river input in the BG-Flood model.
    flow_length_mins : int
        Duration of the river flow in minutes.
    time_to_peak_mins : Union[int, float]
        The time in minutes when flow is at its greatest (reaches maximum).
    maf : bool, optional
        Set to True to obtain MAF-based scenario data or False to obtain ARI-based scenario data.
    ari : int, optional
        The Average Recurrence Interval (ARI) value. Valid options are 5, 10, 20, 50, 100, or 1000.
        Mandatory when 'maf' is set to False, and should be set to None when 'maf' is set to True.
    bound : BoundType, optional
        Set the type of bound (estimate) for the river flow scenario data.
        Valid options include: BoundType.LOWER, BoundType.MIDDLE, or BoundType.UPPER.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the hydrograph data for the requested river flow scenario.

    Raises
    ------
    ValueError
        If the specified 'time_to_peak_mins' is less than half of the river flow duration.
    """
    # TODO: Modify code to incorporate actual method, and align with rainfall and tide data, etc.
    # Determine the minimum time to peak based on the river flow duration
    min_time_to_peak_mins = flow_length_mins / 2
    # Check if the specified time to peak is valid
    if time_to_peak_mins < min_time_to_peak_mins:
        raise ValueError("'time_to_peak_mins' needs to be at least half of 'flow_length_mins' (river flow duration).")
    # Get the river flow scenario data
    river_flow_data = get_river_flow_scenario_data(matched_data, maf, ari, bound)
    # Initialize an empty data dictionary to store hydrograph data
    hydro_data_dict = {
        'target_point_no': [],
        'target_point': [],
        'dem_resolution': [],
        'areakm2': [],
        'mins': [],
        'flow': []
    }
    # Generate hydrograph data for the requested river flow scenario
    for _, row in river_flow_data.iterrows():
        hydro_data_dict['target_point_no'].extend([row['target_point_no']] * 3)
        hydro_data_dict['target_point'].extend([row['target_point']] * 3)
        hydro_data_dict['dem_resolution'].extend([row['dem_resolution']] * 3)
        hydro_data_dict['areakm2'].extend([row['areakm2']] * 3)
        # Generate three different time steps: before peak, at peak, and after peak
        hydro_data_dict['mins'].extend(
            [time_to_peak_mins - min_time_to_peak_mins,
             time_to_peak_mins,
             time_to_peak_mins + min_time_to_peak_mins])
        # Calculate flow values for the hydrograph
        hydro_data_dict['flow'].extend([row['maf'] * 0.1, row['middle'], 0])
    # Create a GeoDataFrame with the hydrograph data dictionary
    hydrograph_data = gpd.GeoDataFrame(hydro_data_dict, geometry="target_point", crs=river_flow_data.crs)
    # Add extra time information columns: hours and seconds
    hydrograph_data['hours'] = hydrograph_data['mins'] / 60
    hydrograph_data['seconds'] = hydrograph_data['mins'] * 60
    # Move the 'flow' column to the last column
    hydrograph_data['flow'] = hydrograph_data.pop('flow')
    return hydrograph_data
