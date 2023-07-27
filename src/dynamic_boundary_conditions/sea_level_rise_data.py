# -*- coding: utf-8 -*-
"""
@Description: This script handles the reading of sea level rise data from the NZ Sea level rise datasets,
              storing the data in the database, and
              retrieving the closest sea level rise data from the database for all locations in the provided tide data.
@Author: sli229
"""

import logging
import pathlib

import geopandas as gpd
import pandas as pd
import pyarrow.csv as csv
from sqlalchemy.engine import Engine

from src import config
from src.digitaltwin import tables

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def get_slr_data_from_nz_searise() -> gpd.GeoDataFrame:
    """
    Read sea level rise data from the NZ Sea level rise datasets and return a GeoDataFrame.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the sea level rise data from the NZ Sea level rise datasets.

    Raises
    ------
    FileNotFoundError
        If the sea level rise data directory does not exist or if there are no CSV files in the specified directory.
    """
    # Get the sea level rise data directory from the environment variable
    slr_data_dir = config.get_env_variable("DATA_DIR_SLR", cast_to=pathlib.Path)
    # Check if the sea level rise data directory exists
    if not slr_data_dir.exists():
        raise FileNotFoundError(f"Sea level rise data directory not found: '{slr_data_dir}'.")
    # Check if there are any CSV files in the specified directory
    if not any(slr_data_dir.glob("*.csv")):
        raise FileNotFoundError(f"Sea level rise data files not found in: {slr_data_dir}")
    # Create an empty list to store the sea level rise datasets
    slr_nz_list = []
    # Loop through each CSV file in the specified directory
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


def store_slr_data_to_db(engine: Engine) -> None:
    """
    Store sea level rise data to the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Define the table name for storing the sea level rise data
    table_name = "sea_level_rise"
    # Check if the table already exists in the database
    if tables.check_table_exists(engine, table_name):
        log.info(f"Table '{table_name}' already exists in the database.")
    else:
        # Get sea level rise data from the NZ Sea level rise datasets
        slr_nz = get_slr_data_from_nz_searise()
        # Store the sea level rise data to the database table
        slr_nz.to_postgis(table_name, engine, index=False, if_exists="replace")
        log.info(f"Stored '{table_name}' data in the database.")


def get_closest_slr_data(engine: Engine, single_query_loc: pd.Series) -> gpd.GeoDataFrame:
    """
    Retrieve the closest sea level rise data for a single query location from the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.

    single_query_loc : pd.Series
        Pandas Series containing the location coordinate and additional information used for retrieval.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the closest sea level rise data for the query location from the database.
    """
    # Create a GeoDataFrame with the query location geometry
    query_loc_geom = gpd.GeoDataFrame(geometry=[single_query_loc["geometry"]], crs=4326)
    # Convert the query location geometry to the desired coordinate reference system (CRS)
    query_loc_geom = query_loc_geom.to_crs(2193).reset_index(drop=True)
    # Prepare the query to retrieve sea level rise data based on the query location.
    # The subquery calculates the distances between the query location and each location in the 'sea_level_rise' table.
    # It then identifies the location with the shortest distance, indicating the closest location to the query location,
    # and retrieves the 'siteid' associated with that closest location, along with its corresponding distance value.
    # The outer query joins the sea_level_rise table with the inner subquery, merging the results to retrieve the
    # relevant data, which includes the calculated distance. By matching the closest location's 'siteid' from the
    # inner subquery with the corresponding data in the sea_level_rise table using the JOIN clause, the outer query
    # obtains the sea level rise data for the closest location, along with its associated distance value.
    query = f"""
    SELECT slr.*, distances.distance
    FROM sea_level_rise AS slr
    JOIN (
        SELECT siteid,
        ST_Distance(ST_Transform(geometry, 2193), ST_GeomFromText('{query_loc_geom["geometry"][0]}', 2193)) AS distance
        FROM sea_level_rise
        ORDER BY distance
        LIMIT 1
    ) AS distances ON slr.siteid = distances.siteid"""
    # Execute the query and retrieve the data as a GeoDataFrame
    query_data = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry")
    # Add the position information to the retrieved data
    query_data["position"] = single_query_loc["position"]
    return query_data


def get_slr_data_from_db(engine: Engine, tide_data: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Retrieve the closest sea level rise data from the database for all locations in the provided tide data.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.

    tide_data : gpd.GeoDataFrame
        A GeoDataFrame containing tide data with added time information (seconds, minutes, hours) and location details.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the closest sea level rise data for all locations in the tide data.
    """
    # Select unique query locations from the tide data
    slr_query_loc = tide_data[['position', 'geometry']].drop_duplicates()
    # Initialize an empty GeoDataFrame to store the closest sea level rise data for all locations
    slr_data = gpd.GeoDataFrame()
    # Iterate over each query location
    for _, row in slr_query_loc.iterrows():
        # Retrieve the closest sea level rise data from the database for the current query location
        query_loc_data = get_closest_slr_data(engine, row)
        # Concatenate the closest sea level rise data for the query location with the overall sea level rise data
        slr_data = pd.concat([slr_data, query_loc_data])
    # Reset the index of the closest sea level rise data
    slr_data = gpd.GeoDataFrame(slr_data).reset_index(drop=True)
    return slr_data
