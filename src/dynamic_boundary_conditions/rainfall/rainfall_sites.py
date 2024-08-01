# -*- coding: utf-8 -*-
"""Fetch rainfall sites data from the HIRDS website and store it in the database."""

import logging

import geopandas as gpd
import pandas as pd
import requests
from sqlalchemy.engine import Engine

from src.digitaltwin import tables

log = logging.getLogger(__name__)


def get_rainfall_sites_data() -> str:
    """
    Get rainfall sites data from the HIRDS website.

    Returns
    -------
    str
        The rainfall sites data as a string.
    """
    url = "https://api.niwa.co.nz/hirds/sites"
    headers = {
        "Referer": "https://hirds.niwa.co.nz/"
    }
    # Send HTTP GET request to the specified URL with headers
    response = requests.get(url, headers=headers)
    # Return the response content as a text string
    sites_data = response.text
    return sites_data


def get_rainfall_sites_in_df() -> gpd.GeoDataFrame:
    """
    Get rainfall sites data from the HIRDS website and transform it into a GeoDataFrame.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the rainfall sites data.
    """
    # Retrieve rainfall sites data
    sites_data = get_rainfall_sites_data()
    # Convert JSON data to DataFrame
    sites_df = pd.read_json(sites_data)
    # Create geometry column from longitude and latitude
    sites_geometry = gpd.points_from_xy(sites_df["longitude"], sites_df["latitude"], crs=4326)
    # Create GeoDataFrame with sites data and geometry
    sites_with_geometry = gpd.GeoDataFrame(sites_df, geometry=sites_geometry)
    return sites_with_geometry


def rainfall_sites_to_db(engine: Engine) -> None:
    """
    Store rainfall sites data from the HIRDS website in the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    """
    table_name = "rainfall_sites"
    # Check if the table already exists in the database
    if tables.check_table_exists(engine, table_name):
        log.info(f"'{table_name}' data already exists in the database.")
    else:
        # Get rainfall sites data
        log.info(f"Fetching '{table_name}' data from the HIRDS website https://hirds.niwa.co.nz/.")
        sites = get_rainfall_sites_in_df()
        # Store rainfall sites data in the database
        log.info(f"Adding '{table_name}' data to the database.")
        sites.to_postgis(f'{table_name}', engine, if_exists='replace', index=False)
