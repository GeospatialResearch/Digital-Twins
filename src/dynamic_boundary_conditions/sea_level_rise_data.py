# -*- coding: utf-8 -*-
"""
@Description:
@Author: sli229
"""

import logging
import pathlib

import geopandas as gpd
import pandas as pd
import pyarrow.csv as csv

from src import config
from src.digitaltwin import setup_environment
from src.dynamic_boundary_conditions import main_tide_slr, tide_query_location, tide_data_from_niwa
from src.dynamic_boundary_conditions.tide_enum import ApproachType

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def get_slr_data_from_nz_searise(slr_data_dir: pathlib.Path) -> pd.DataFrame:
    """
    Returns a Pandas DataFrame that is a concatenation of all the sea level rise data located in the
    sea level rise data directory.
    """
    # Check if the sea level rise data directory exists, if not, raise an error
    if not slr_data_dir.exists():
        raise FileNotFoundError(f"Sea level rise data directory not found: '{slr_data_dir}'.")
    # Check if there are any CSV files in the specified directory
    if not any(slr_data_dir.glob("*.csv")):
        raise FileNotFoundError(f"Sea level rise data files not found in: {slr_data_dir}")
    # Loop through each CSV file in the specified directory
    slr_nz_list = []
    for file_path in slr_data_dir.glob("*.csv"):
        # Read the CSV file into a pandas DataFrame using pyarrow
        slr_region = csv.read_csv(file_path).to_pandas()
        # Extract the region name from the file name and add it as a new column in the DataFrame
        file_name = file_path.stem
        start_index = file_name.find('projections_') + len('projections_')
        end_index = file_name.find('_region')
        region_name = file_name[start_index:end_index]
        slr_region['region'] = region_name
        # Append the DataFrame to the list
        slr_nz_list.append(slr_region)
        # Log that the file has been successfully loaded
        log.info(f"{file_path.name} data file has been successfully loaded.")
    # Concatenate all the dataframes in the list and add geometry column
    slr_nz = pd.concat(slr_nz_list, axis=0).reset_index(drop=True)
    geometry = gpd.points_from_xy(slr_nz['lon'], slr_nz['lat'], crs=4326)
    slr_nz_with_geom = gpd.GeoDataFrame(slr_nz, geometry=geometry)
    # Convert all column names to lowercase
    slr_nz_with_geom.columns = slr_nz_with_geom.columns.str.lower()
    return slr_nz_with_geom


def store_slr_data_to_db(engine, slr_data_dir: pathlib.Path):
    if main_tide_slr.check_table_exists(engine, "sea_level_rise"):
        log.info("Table 'sea_level_rise_data' already exists in the database.")
    else:
        slr_nz = get_slr_data_from_nz_searise(slr_data_dir)
        slr_nz.to_postgis("sea_level_rise", engine, index=False, if_exists="replace")
        log.info("Added Sea Level Rise data to database.")


def get_slr_data_from_db(engine, single_query_loc: pd.Series) -> gpd.GeoDataFrame:
    query_loc_geom = gpd.GeoDataFrame(geometry=[single_query_loc["geometry"]], crs=4326)
    query_loc_geom = query_loc_geom.to_crs(2193).reset_index(drop=True)
    query = f"""
    SELECT slr.*, distances.distance
    FROM sea_level_rise AS slr
    JOIN (
        SELECT siteid, ST_Distance(ST_Transform(geometry, 2193),
        ST_GeomFromText('{query_loc_geom["geometry"][0]}', 2193)) AS distance
        FROM sea_level_rise
        ORDER BY distance
        LIMIT 1
    ) AS distances ON slr.siteid = distances.siteid"""
    query_data = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry")
    query_data["position"] = single_query_loc["position"]
    return query_data


def get_closest_slr_data(engine, tide_data: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    slr_query_loc = tide_data[['position', 'geometry']].drop_duplicates()
    slr_data = gpd.GeoDataFrame()
    for index, row in slr_query_loc.iterrows():
        query_loc_data = get_slr_data_from_db(engine, row)
        slr_data = pd.concat([slr_data, query_loc_data])
    slr_data = slr_data.reset_index(drop=True)
    return slr_data


def main():
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
        interval_mins=10)

    # Store sea level rise data to database
    slr_data_dir = config.get_env_variable("DATA_DIR_SLR", cast_to=pathlib.Path)
    store_slr_data_to_db(engine, slr_data_dir)
    # Get closest sea level rise site data from database
    slr_data = get_closest_slr_data(engine, tide_data_king)
    print(slr_data)


if __name__ == "__main__":
    main()
