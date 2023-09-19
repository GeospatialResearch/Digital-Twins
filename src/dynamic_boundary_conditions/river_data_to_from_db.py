# -*- coding: utf-8 -*-
"""
This script handles the reading of REC1 data from the NIWA REC1 dataset,
storing the data in the database, and retrieving the REC1 data from the database.
"""

import logging
import pathlib

import geopandas as gpd
import pandas as pd
from sqlalchemy.engine import Engine

from src import config
from src.digitaltwin import tables

log = logging.getLogger(__name__)


def get_rec1_data_from_niwa() -> gpd.GeoDataFrame:
    """
    Reads REC1 data from the NIWA REC1 dataset and returns a GeoDataFrame.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the REC1 data from the NZ REC1 dataset.

    Raises
    ------
    FileNotFoundError
        If the REC1 data directory does not exist or if there are no Shapefiles in the specified directory.
    """
    # Get the REC1 data directory from the environment variable
    rec1_data_dir = config.get_env_variable("DATA_DIR_REC1", cast_to=pathlib.Path)
    # Check if the REC1 data directory exists
    if not rec1_data_dir.exists():
        raise FileNotFoundError(f"REC1 data directory not found: {rec1_data_dir}")
    # Check if there are any Shapefiles in the specified directory
    if not any(rec1_data_dir.glob("*.shp")):
        raise FileNotFoundError(f"REC1 data files not found: {rec1_data_dir}")
    # Find the path of the first file in `rec1_data_dir` that ends with .shp
    rec1_file_path = next(rec1_data_dir.glob('*.shp'))
    # Read the Shapefile into a GeoDataFrame
    rec1_nz = gpd.read_file(rec1_file_path)
    # Convert column names to lowercase for consistency
    rec1_nz.columns = rec1_nz.columns.str.lower()
    return rec1_nz


def store_rec1_data_to_db(engine: Engine) -> None:
    """
    Store REC1 data to the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Define the table name for storing the REC1 data
    table_name = "rec1_data"
    # Check if the table already exists in the database
    if tables.check_table_exists(engine, table_name):
        log.info(f"Table '{table_name}' already exists in the database.")
    else:
        # Get REC1 data from the NZ REC1 dataset
        rec1_nz = get_rec1_data_from_niwa()
        # Store the REC1 data to the database table
        rec1_nz.to_postgis(table_name, engine, index=False, if_exists="replace")
        log.info(f"Stored '{table_name}' data in the database.")


def get_rec1_data_from_db(
        engine: Engine,
        catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Retrieve REC1 data from the database for the specified catchment area.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the retrieved REC1 data for the specified catchment area.
    """
    # Extract the geometry of the catchment area
    catchment_polygon = catchment_area["geometry"][0]
    # Query to retrieve sea-draining catchments that intersect with the catchment polygon
    sea_drain_query = f"""
    SELECT *
    FROM sea_draining_catchments AS sdc
    WHERE ST_Intersects(sdc.geometry, ST_GeomFromText('{catchment_polygon}', 2193));
    """
    # Create a GeoDataFrame from the sea-draining catchment data retrieved from the database
    sdc_data = gpd.GeoDataFrame.from_postgis(sea_drain_query, engine, geom_col="geometry")
    # Unify the sea-draining catchment polygons into a single polygon
    sdc_polygon = sdc_data.unary_union
    # Create a GeoDataFrame representing the unified sea-draining catchment area
    sdc_area = gpd.GeoDataFrame(geometry=[sdc_polygon], crs=sdc_data.crs)
    # Combine the sea-draining catchment area with the input catchment area to create a final unified polygon
    combined_polygon = pd.concat([sdc_area, catchment_area]).unary_union
    # Query to retrieve REC1 data that intersects with the combined polygon
    rec1_query = f"""
    SELECT *
    FROM rec1_data AS rec
    WHERE ST_Intersects(rec.geometry, ST_GeomFromText('{combined_polygon}', 2193));
    """
    # Execute the query and retrieve the REC1 data from the database
    rec1_data = gpd.GeoDataFrame.from_postgis(rec1_query, engine, geom_col="geometry")
    # Remove any duplicate records from the REC1 data
    rec1_data = rec1_data.drop_duplicates()
    return rec1_data
