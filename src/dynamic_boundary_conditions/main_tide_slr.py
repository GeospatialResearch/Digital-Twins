# -*- coding: utf-8 -*-
"""
@Description:
@Author: sli229
"""

import logging
import pathlib

from src import config
from src.digitaltwin import setup_environment
from src.dynamic_boundary_conditions.tide_enum import DatumType, ApproachType
from src.dynamic_boundary_conditions import tide_query_location, tide_data_from_niwa
from src.dynamic_boundary_conditions import sea_level_rise_data, tide_slr_combine

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


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
    tide_data_king = tide_data_from_niwa.get_tide_data(
        approach=ApproachType.KING_TIDE,
        api_key=niwa_api_key,
        datum=datum,
        tide_query_loc=tide_query_loc,
        tide_length_mins=2880,
        interval_mins=10)
    # Store sea level rise data to database and get closest sea level rise site data from database
    sea_level_rise_data.store_slr_data_to_db(engine)
    slr_data = sea_level_rise_data.get_closest_slr_data(engine, tide_data_king)
    # Combine tide and sea level rise data
    tide_slr_data = tide_slr_combine.get_combined_tide_slr_data(
        tide_data=tide_data_king,
        slr_data=slr_data,
        proj_year=2030,
        confidence_level='low',
        ssp_scenario='SSP1-2.6',
        add_vlm=False,
        percentile=50)
    print(tide_slr_data)


if __name__ == "__main__":
    main()
