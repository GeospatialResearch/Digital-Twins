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
    slr_data['confidence_level'] = slr_data['measurementname'].str.extract(r'(low|medium) confidence')
    slr_data['ssp_scenario'] = slr_data['measurementname'].str.extract(r'(\w+-\d\.\d)')
    slr_data['add_vlm'] = slr_data['measurementname'].str.contains('\+ VLM')
    return slr_data


def get_slr_scenario_data(
        slr_data: gpd.GeoDataFrame,
        confidence_level: str,
        ssp_scenario: str,
        add_vlm: bool,
        percentile: int) -> gpd.GeoDataFrame:
    # Get the valid percentiles
    percentile_cols = [col for col in slr_data.columns if re.match(r'^p\d+', col)]
    valid_percentile = [int(col[1:]) for col in percentile_cols]
    if percentile not in valid_percentile:
        raise ValueError(f"Invalid value '{percentile}' for percentile. Must be one of {valid_percentile}.")
    # Split measurementname column out
    slr_data = split_slr_measurementname_column(slr_data)
    # Get the valid confidence levels
    valid_conf_level = slr_data['confidence_level'].unique().tolist()
    if confidence_level not in valid_conf_level:
        raise ValueError(f"Invalid value '{confidence_level}' for confidence_level. Must be one of {valid_conf_level}.")
    slr_scenario = slr_data[slr_data["confidence_level"] == confidence_level]
    # Get the valid ssp scenarios
    valid_ssp_scenario = slr_scenario['ssp_scenario'].unique().tolist()
    if ssp_scenario not in valid_ssp_scenario:
        raise ValueError(f"Invalid value '{ssp_scenario}' for ssp_scenario. Must be one of {valid_ssp_scenario}.")
    slr_scenario = slr_scenario[slr_scenario['ssp_scenario'] == ssp_scenario]
    # Get the VLM and percentile data
    slr_scenario = slr_scenario[slr_scenario['add_vlm'] == add_vlm]
    percentile_col = f"p{percentile}"
    slr_scenario = slr_scenario[['siteid', 'year', percentile_col, 'geometry', 'position']]
    return slr_scenario


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
    slr_scenario = get_slr_scenario_data(
        slr_data, confidence_level='medium', ssp_scenario='SSP3-7.0', add_vlm=False, percentile=50)
    print(slr_scenario)
    print(type(slr_scenario))


if __name__ == "__main__":
    main()
