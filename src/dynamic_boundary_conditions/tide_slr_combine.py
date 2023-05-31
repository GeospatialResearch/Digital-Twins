# -*- coding: utf-8 -*-
"""
@Description:
@Author: sli229
"""

import re

import geopandas as gpd
import pandas as pd
import numpy as np
from scipy.interpolate import interp1d
import shapely.wkt


def split_slr_measurementname_column(slr_data: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    slr_data_split = slr_data.copy()
    slr_data_split['confidence_level'] = slr_data_split['measurementname'].str.extract(r'(low|medium) confidence')
    slr_data_split['ssp_scenario'] = slr_data_split['measurementname'].str.extract(r'(\w+-\d\.\d)')
    slr_data_split['add_vlm'] = slr_data_split['measurementname'].str.contains(r'\+ VLM')
    return slr_data_split


def get_slr_scenario_data(
        slr_data: gpd.GeoDataFrame,
        confidence_level: str,
        ssp_scenario: str,
        add_vlm: bool,
        percentile: int) -> gpd.GeoDataFrame:
    # Split measurementname column out
    slr_data_split = split_slr_measurementname_column(slr_data)
    # Get the requested confidence level data
    valid_conf_level = slr_data_split['confidence_level'].unique().tolist()
    if confidence_level not in valid_conf_level:
        raise ValueError(f"Invalid value '{confidence_level}' for confidence_level. Must be one of {valid_conf_level}.")
    slr_scenario = slr_data_split[slr_data_split["confidence_level"] == confidence_level]
    # Get the requested ssp scenario data
    valid_ssp_scenario = slr_scenario['ssp_scenario'].unique().tolist()
    if ssp_scenario not in valid_ssp_scenario:
        raise ValueError(f"Invalid value '{ssp_scenario}' for ssp_scenario. Must be one of {valid_ssp_scenario}.")
    slr_scenario = slr_scenario[slr_scenario['ssp_scenario'] == ssp_scenario]
    # Get the requested add_vlm data
    valid_add_vlm = slr_scenario['add_vlm'].unique().tolist()
    if add_vlm not in valid_add_vlm:
        raise ValueError(f"Invalid value '{add_vlm}' for add_vlm. Must be one of {valid_add_vlm}.")
    slr_scenario = slr_scenario[slr_scenario['add_vlm'] == add_vlm]
    # Get the requested percentile data
    percentile_cols = [col for col in slr_data.columns if re.match(r'^p\d+', col)]
    valid_percentile = [int(col[1:]) for col in percentile_cols]
    if percentile not in valid_percentile:
        raise ValueError(f"Invalid value '{percentile}' for percentile. Must be one of {valid_percentile}.")
    slr_scenario = slr_scenario[['siteid', 'year', f"p{percentile}", 'geometry', 'position']]
    # Get the final requested sea level rise scenario data
    slr_scenario_data = slr_scenario.rename(columns={f"p{percentile}": "slr_metres"}).reset_index(drop=True)
    return slr_scenario_data


def get_interpolated_slr_scenario_data(
        slr_scenario_data: gpd.GeoDataFrame,
        increment_year: int = 1,
        interp_method: str = 'linear') -> gpd.GeoDataFrame:
    # Group the data
    grouped = slr_scenario_data.groupby(['siteid', slr_scenario_data['geometry'].to_wkt(), 'position'])
    slr_interp_scenario = gpd.GeoDataFrame()
    for group_name, group_data in grouped:
        site_id, geometry, position = group_name
        # Interpolate the data
        group_years = group_data['year']
        group_years_new = np.arange(group_years.iloc[0], group_years.iloc[-1] + increment_year, increment_year)
        group_years_new = pd.Series(group_years_new, name='year')
        f_func = interp1d(group_years, group_data['slr_metres'], kind=interp_method)
        group_data_new = pd.Series(f_func(group_years_new), name='slr_metres')
        group_data_interp = pd.concat([group_years_new, group_data_new], axis=1)
        group_data_interp[['siteid', 'geometry', 'position']] = site_id, shapely.wkt.loads(geometry), position
        group_data_interp = gpd.GeoDataFrame(group_data_interp, crs=group_data.crs)
        slr_interp_scenario = pd.concat([slr_interp_scenario, group_data_interp])
    slr_interp_scenario = slr_interp_scenario.reset_index(drop=True)
    return slr_interp_scenario


def add_slr_to_tide(
        tide_data: gpd.GeoDataFrame,
        slr_interp_scenario: gpd.GeoDataFrame,
        proj_year: int) -> pd.DataFrame:
    tide_df = tide_data.copy()
    tide_df['year'] = tide_df['datetime_nz'].dt.year
    tide_df = tide_df[['seconds', 'year', 'tide_metres', 'position']]
    grouped = tide_df.groupby(['year', 'position'])
    tide_slr_data = gpd.GeoDataFrame()
    for group_name, group_data in grouped:
        current_year, position = group_name
        current_filt = (slr_interp_scenario['year'] == current_year) & (slr_interp_scenario['position'] == position)
        proj_filt = (slr_interp_scenario['year'] == proj_year) & (slr_interp_scenario['position'] == position)
        current_slr_metres = slr_interp_scenario[current_filt]['slr_metres'].iloc[0]
        proj_slr_metres = slr_interp_scenario[proj_filt]['slr_metres'].iloc[0]
        group_data['slr_metres'] = proj_slr_metres - current_slr_metres
        tide_slr_data = pd.concat([tide_slr_data, group_data])
    tide_slr_data['tide_slr_metres'] = tide_slr_data['tide_metres'] + tide_slr_data['slr_metres']
    tide_slr_data = tide_slr_data[['seconds', 'tide_slr_metres', 'position']]
    tide_slr_data = tide_slr_data.reset_index(drop=True)
    return tide_slr_data


def get_combined_tide_slr_data(
        tide_data: gpd.GeoDataFrame,
        slr_data: gpd.GeoDataFrame,
        proj_year: int,
        confidence_level: str,
        ssp_scenario: str,
        add_vlm: bool,
        percentile: int,
        increment_year: int = 1,
        interp_method: str = 'linear') -> pd.DataFrame:
    slr_scenario_data = get_slr_scenario_data(slr_data, confidence_level, ssp_scenario, add_vlm, percentile)
    slr_interp_scenario = get_interpolated_slr_scenario_data(slr_scenario_data, increment_year, interp_method)
    tide_slr_data = add_slr_to_tide(tide_data, slr_interp_scenario, proj_year)
    return tide_slr_data
