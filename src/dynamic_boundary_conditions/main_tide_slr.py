# -*- coding: utf-8 -*-
"""
@Description:
@Author: sli229
"""

import logging
import pathlib
from typing import Union

import sqlalchemy
import geopandas as gpd
from shapely.geometry import box

from src import config
from src.digitaltwin import setup_environment
from src.dynamic_boundary_conditions.tide_enum import ApproachType
from src.dynamic_boundary_conditions import (
    tide_query_location,
    tide_data_from_niwa,
    sea_level_rise_data,
    tide_slr_combine,
    tide_slr_model_input
)

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def write_nz_bbox_to_file(engine, file_name: str = "nz_bbox.geojson"):
    file_path = pathlib.Path.cwd() / file_name
    if not file_path.is_file():
        query = "SELECT * FROM region_geometry"
        region_geom = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry")
        nz_geom = region_geom.query('shape_area == shape_area.max()').reset_index(drop=True)
        min_x, min_y, max_x, max_y = nz_geom.total_bounds
        bbox = box(min_x, min_y, max_x, max_y)
        nz_bbox = gpd.GeoDataFrame(geometry=[bbox], crs=2193)
        nz_bbox.to_file(file_name, driver="GeoJSON")


def get_catchment_area(
        catchment_area: gpd.GeoDataFrame,
        to_crs: int = 2193) -> gpd.GeoDataFrame:
    catchment_area = catchment_area.to_crs(to_crs)
    return catchment_area


def check_table_exists(engine, db_table_name: str) -> bool:
    """
    Check if table exists in the database.

    Parameters
    ----------
    engine
        Engine used to connect to the database.
    db_table_name : str
        Database table name.
    """
    insp = sqlalchemy.inspect(engine)
    table_exists = insp.has_table(db_table_name, schema="public")
    return table_exists


def remove_existing_boundary_input(bg_flood_dir: pathlib.Path):
    # iterate through all files in the directory
    for file_path in bg_flood_dir.glob('*_bnd.txt'):
        # remove the file
        file_path.unlink()


def main(selected_polygon_gdf: gpd.GeoDataFrame):
    try:
        # Connect to the database
        engine = setup_environment.get_database()
        write_nz_bbox_to_file(engine)
        # Get catchment area
        catchment_area = get_catchment_area(selected_polygon_gdf, to_crs=2193)
        # BG-Flood Model Directory
        bg_flood_dir = config.get_env_variable("FLOOD_MODEL_DIR", cast_to=pathlib.Path)
        # Remove existing tide model input files
        remove_existing_boundary_input(bg_flood_dir)

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
        tide_slr_model_input.generate_uniform_boundary_input(bg_flood_dir, tide_slr_data)

    except tide_query_location.NoTideDataException as error:
        log.info(error)


if __name__ == "__main__":
    sample_polygon = gpd.GeoDataFrame.from_file("selected_polygon.geojson")
    main(sample_polygon)
