# -*- coding: utf-8 -*-
"""
@Script name: rainfall_sites.py
@Description: Fetch rainfall sites data from the HIRDS website and store it to the database.
@Author: pkh35
@Date: 23/12/2021
@Last modified by: sli229
@Last modified date: 5/12/2022
"""

import requests
from requests.structures import CaseInsensitiveDict
import pandas as pd
import geopandas as gpd
import logging
from geoalchemy2 import Geometry
from src.digitaltwin import setup_environment
from src.dynamic_boundary_conditions import hirds_rainfall_data_to_db

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def get_rainfall_sites_data() -> str:
    """Get rainfall sites data from the HIRDS website using HTTP request."""
    url = "https://api.niwa.co.nz/hirds/sites"
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
    response = requests.get(url, headers=headers)
    sites_data = response.text
    return sites_data


def get_rainfall_sites_in_df() -> gpd.GeoDataFrame:
    """Get rainfall sites data from the HIRDS website and transform to GeoDataFrame format."""
    sites_data = get_rainfall_sites_data()
    sites_df = pd.read_json(sites_data)
    sites_geometry = gpd.points_from_xy(sites_df["longitude"], sites_df["latitude"], crs="EPSG:4326")
    sites_with_geometry = gpd.GeoDataFrame(sites_df, geometry=sites_geometry)
    return sites_with_geometry


def rainfall_sites_to_db(engine):
    """
    Storing rainfall sites data from the HIRDS website in the database.

    Parameters
    ----------
    engine
        Engine used to connect to the database.
    sites : gpd.GeoDataFrame
        Rainfall sites in New Zealand.
    """
    if hirds_rainfall_data_to_db.check_table_exists(engine, "rainfall_sites"):
        log.info("Rainfall sites data already exists in the database.")
    else:
        sites = get_rainfall_sites_in_df()
        sites.to_postgis('rainfall_sites', engine, if_exists='replace', index=False,
                         dtype={'geometry': Geometry(geometry_type='POINT', srid=4326)})
        log.info("Stored rainfall sites data in the database.")


def main():
    # Connect to the database
    engine = setup_environment.get_database()
    # Fetch rainfall sites data from the HIRDS website and store it to the database
    rainfall_sites_to_db(engine)


if __name__ == "__main__":
    main()
