# -*- coding: utf-8 -*-
"""
@Description:
@Author: sli229
"""

import logging
import pathlib
from typing import Tuple, Union, Optional, List
from datetime import date, timedelta

import re
import geopandas as gpd
import pandas as pd
import numpy as np
from scipy.interpolate import interp1d

from src import config
from src.digitaltwin import setup_environment
from src.dynamic_boundary_conditions.tide_enum import DatumType, ApproachType
from src.dynamic_boundary_conditions import tide_query_location, tide_data_from_niwa, sea_level_rise_data

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def split_slr_measurementname_column(slr_data: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    slr_data_split = slr_data.copy()
    slr_data_split['confidence_level'] = slr_data_split['measurementname'].str.extract(r'(low|medium) confidence')
    slr_data_split['ssp_scenario'] = slr_data_split['measurementname'].str.extract(r'(\w+-\d\.\d)')
    slr_data_split['add_vlm'] = slr_data_split['measurementname'].str.contains('\+ VLM')
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
    # Get the final requested sea level rise scenario data
    slr_scenario_data = slr_scenario[['siteid', 'year', f"p{percentile}", 'geometry', 'position']]
    slr_scenario_data = slr_scenario_data.rename(columns={f"p{percentile}": "slr_metres"}).reset_index(drop=True)
    return slr_scenario_data


def get_interpolated_slr_scenario_data(
        slr_scenario_data: gpd.GeoDataFrame,
        increment_year: int = 1,
        interp_method: str = 'linear') -> gpd.GeoDataFrame:
    # Group the data
    slr_interp_scenario = gpd.GeoDataFrame()
    grouped = slr_scenario_data.groupby(['siteid', 'geometry', 'position'])
    for group_name, group_data in grouped:
        site_id, geometry, position = group_name
        # Interpolate the data
        group_years = group_data['year']
        group_years_new = np.arange(group_years.iloc[0], group_years.iloc[-1] + increment_year, increment_year)
        group_years_new = pd.Series(group_years_new, name='year')
        f_func = interp1d(group_years, group_data['slr_metres'], kind=interp_method)
        group_data_new = pd.Series(f_func(group_years_new), name='slr_metres')
        group_data_interp = pd.concat([group_years_new, group_data_new], axis=1)
        group_data_interp[['siteid', 'geometry', 'position']] = site_id, geometry, position
        group_data_interp = gpd.GeoDataFrame(group_data_interp, crs=group_data.crs)
        slr_interp_scenario = pd.concat([slr_interp_scenario, group_data_interp])
    return slr_interp_scenario


def combine_tide_slr_data(
        tide_data: gpd.GeoDataFrame,
        slr_interp_scenario: gpd.GeoDataFrame,
        proj_year: int) -> pd.DataFrame:
    tide_df = tide_data.copy()
    tide_df['year'] = tide_df['datetime_nz'].dt.year
    tide_df = tide_df[['datetime_nz', 'year', 'tide_metres', 'position']]
    grouped = tide_df.groupby(['year', 'position'])
    tide_slr_data = gpd.GeoDataFrame()
    for group_name, group_data in grouped:
        current_year, position = group_name
        current_filt = (slr_interp_scenario['year'] == current_year) & (slr_interp_scenario['position'] == position)
        proj_filt = (slr_interp_scenario['year'] == proj_year) & (slr_interp_scenario['position'] == position)
        current_slr_metres = slr_interp_scenario[current_filt]['slr_metres'].iloc[0]
        proj_slr_metres = slr_interp_scenario[proj_filt]['slr_metres'].iloc[0]
        group_data['addon_slr_metres'] = proj_slr_metres - current_slr_metres
        tide_slr_data = pd.concat([tide_slr_data, group_data])
    tide_slr_data['tide_slr_metres'] = tide_slr_data['tide_metres'] + tide_slr_data['addon_slr_metres']
    tide_slr_data = tide_slr_data[['datetime_nz', 'tide_slr_metres', 'position']]
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
    tide_slr_data = combine_tide_slr_data(tide_data, slr_interp_scenario, proj_year)
    return tide_slr_data


def main():
    # Get StatsNZ and NIWA api key
    stats_nz_api_key = config.get_env_variable("StatsNZ_API_KEY")
    niwa_api_key = config.get_env_variable("NIWA_API_KEY")
    # Connect to the database
    engine = setup_environment.get_database()
    tide_query_location.write_nz_bbox_to_file(engine)
    # Catchment polygon
    catchment_file = pathlib.Path(r"selected_polygon.geojson")
    catchment_area = tide_query_location.get_catchment_area(catchment_file)
    # Store regional council clipped data in the database
    tide_query_location.regional_council_clipped_to_db(engine, stats_nz_api_key, 111181)
    # Get regions (clipped) that intersect with the catchment area from the database
    regions_clipped = tide_query_location.get_regions_clipped_from_db(engine, catchment_area)
    tide_query_loc = tide_query_location.get_tide_query_locations(
        engine, catchment_area, regions_clipped, distance_km=1)
    # Specify the datum query parameter
    datum = DatumType.LAT
    # Get tide data
    tide_data = tide_data_from_niwa.get_tide_data(
        approach=ApproachType.KING_TIDE,
        api_key=niwa_api_key,
        datum=datum,
        tide_query_loc=tide_query_loc,
        start_date=date(2023, 1, 23),
        total_days=3,  # used for PERIOD_TIDE
        tide_length_mins=2880,  # used for KING_TIDE
        interval=10)
    # Store sea level rise data to database and get closest sea level rise site data from database
    sea_level_rise_data.store_slr_data_to_db(engine)
    slr_data = sea_level_rise_data.get_closest_slr_data(engine, tide_data)
    # Combine tide and sea level rise data
    tide_slr_data = get_combined_tide_slr_data(
        tide_data=tide_data,
        slr_data=slr_data,
        proj_year=2030,
        confidence_level='low',
        ssp_scenario='SSP1-2.6',
        add_vlm=False,
        percentile=50)
    print(tide_slr_data)


if __name__ == "__main__":
    main()
