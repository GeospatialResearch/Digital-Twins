# -*- coding: utf-8 -*-
"""
@Description:
@Author: sli229
"""

import logging
import pathlib

import pandas as pd

from src import config
from src.digitaltwin import setup_environment
from src.dynamic_boundary_conditions.tide_enum import ApproachType
from src.dynamic_boundary_conditions import (
    main_tide_slr,
    tide_query_location,
    tide_data_from_niwa,
    sea_level_rise_data,
    tide_slr_combine
)

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def remove_existing_boundary_input(bg_flood_dir: pathlib.Path):
    # iterate through all files in the directory
    for file_path in bg_flood_dir.glob('*_bnd.txt'):
        # remove the file
        file_path.unlink()


def generate_uniform_boundary_input(bg_flood_dir: pathlib.Path, tide_slr_data: pd.DataFrame):
    remove_existing_boundary_input(bg_flood_dir)
    grouped = tide_slr_data.groupby('position')
    for position, group_data in grouped:
        input_data = group_data[['seconds', 'tide_slr_metres']]
        file_path = bg_flood_dir / f"{position}_bnd.txt"
        input_data.to_csv(file_path, sep='\t', index=False, header=False)
        # Add "# Water level boundary" line at the beginning of the file
        with open(file_path, 'r+') as file:
            content = file.read()
            file.seek(0, 0)
            file.write('# Water level boundary\n' + content)
    log.info(f"Successfully generated the uniform boundary input for BG-Flood. Located in: {bg_flood_dir}")


def main():
    try:
        # Connect to the database
        engine = setup_environment.get_database()
        main_tide_slr.write_nz_bbox_to_file(engine)
        # Get catchment area
        catchment_area = main_tide_slr.get_catchment_area("selected_polygon.geojson")

        # Store regional council clipped data in the database
        tide_query_location.store_regional_council_clipped_to_db(engine, layer_id=111181)
        # Get regional council clipped data that intersect with the catchment area from the database
        regions_clipped = tide_query_location.get_regional_council_clipped_from_db(engine, catchment_area)
        # Get the location (coordinates) to fetch tide data for
        tide_query_loc = tide_query_location.get_tide_query_locations(engine, catchment_area, regions_clipped)

        # Get tide data
        tide_data_king = tide_data_from_niwa.get_tide_data(
            tide_query_loc=tide_query_loc,
            approach=ApproachType.KING_TIDE,
            tide_length_mins=2880,
            time_to_peak_mins=1440,
            interval_mins=10)

        # Store sea level rise data to database
        slr_data_dir = config.get_env_variable("DATA_DIR_SLR", cast_to=pathlib.Path)
        sea_level_rise_data.store_slr_data_to_db(engine, slr_data_dir)
        # Get closest sea level rise site data from database
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

        # Generate the model input for BG-Flood
        bg_flood_dir = config.get_env_variable("FLOOD_MODEL_DIR", cast_to=pathlib.Path)
        generate_uniform_boundary_input(bg_flood_dir, tide_slr_data)

    except tide_query_location.NoTideDataException as error:
        log.info(error)


if __name__ == "__main__":
    main()
