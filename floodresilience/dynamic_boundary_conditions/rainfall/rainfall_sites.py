# -*- coding: utf-8 -*-
"""Fetch rainfall sites data from the HIRDS website and store it in the database."""

import logging

import geopandas as gpd
import pandas as pd
import requests
from requests.structures import CaseInsensitiveDict
from sqlalchemy.engine import Engine

from src.digitaltwin import tables

log = logging.getLogger(__name__)


def get_hirds_headers() -> CaseInsensitiveDict:
    """
    Generate a set of HTTP headers for making requests to HIRDS.

    Returns
    -------
    CaseInsensitiveDict
        A dictionary containing HTTP headers required for requests to HIRDS.
    """
    headers = CaseInsensitiveDict()
    headers["Accept"] = "application/json, text/plain, */*"
    headers["Accept-Language"] = "en-GB,en-US;q=0.9,en;q=0.8"
    headers["Connection"] = "keep-alive"
    headers["Origin"] = "https://hirds.niwa.co.nz"
    headers["Referer"] = "https://hirds.niwa.co.nz/"
    headers["sec-ch-ua"] = '"" Not A;Brand";v="99", "Chromium";v="96", "Google Chrome";v="96""'
    headers["sec-ch-ua-mobile"] = "?0"
    headers["sec-ch-ua-platform"] = "Windows"
    headers["Sec-Fetch-Dest"] = "empty"
    headers["Sec-Fetch-Mode"] = "cors"
    headers["Sec-Fetch-Site"] = "same-site"
    headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)\
                Chrome/96.0.4664.45 Safari/537.36"
    return headers


def get_rainfall_sites_data() -> str:
    """
    Get rainfall sites data from the HIRDS website.

    Returns
    -------
    str
        The rainfall sites data as a string.
    """
    url = "https://api.niwa.co.nz/hirds/sites"
    headers = get_hirds_headers()
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
