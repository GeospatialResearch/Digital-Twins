# -*- coding: utf-8 -*-
"""
@Script name: rainfall_sites.py
@Description: Store rainfall sites data from the HIRDS website in the database.
@Author: pkh35
@Date: 23/12/2021
@Last modified by: sli229
@Last modified date: 28/09/2022
"""

import requests
from requests.structures import CaseInsensitiveDict
import pandas as pd
import geopandas as gpd
import logging
from shapely.geometry import Polygon
from geoalchemy2 import Geometry
from src.digitaltwin import setup_environment
from src.dynamic_boundary_conditions import hirds_rainfall_data_to_db

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def get_rainfall_sites_data() -> gpd.GeoDataFrame:
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
    sites_df = pd.read_json(response.text)
    sites_geometry = gpd.points_from_xy(sites_df["longitude"], sites_df["latitude"], crs="EPSG:4326")
    sites_with_geometry = gpd.GeoDataFrame(sites_df, geometry=sites_geometry)
    return sites_with_geometry


def rainfall_sites_to_db(engine, sites: gpd.GeoDataFrame):
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
        sites.to_postgis('rainfall_sites', engine, if_exists='replace', index=False,
                         dtype={'geometry': Geometry(geometry_type='POINT', srid=4326)})
        log.info("Stored rainfall sites data in the database.")


def get_new_zealand_boundary(engine) -> Polygon:
    """
    Get the boundary geometry of New Zealand from the 'region_geometry' table in the database.

    Parameters
    ----------
    engine
        Engine used to connect to the database.
    """
    query = "SELECT geometry AS geom FROM region_geometry WHERE regc2021_v1_00_name='New Zealand'"
    nz_boundary = gpd.GeoDataFrame.from_postgis(query, engine, crs=2193)
    nz_boundary = nz_boundary.to_crs(4326)
    nz_boundary_polygon = nz_boundary["geom"][0]
    return nz_boundary_polygon


def get_sites_locations(engine, catchment: Polygon) -> gpd.GeoDataFrame:
    """
    Get the rainfall sites' locations within the catchment area from the database and return the required data in
    GeoDataFrame format.

    Parameters
    ----------
    engine
        Engine used to connect to the database.
    catchment : Polygon
        New Zealand boundary catchment polygon.
    """
    # Get all rainfall sites within the New Zealand catchment area.
    query = f"""SELECT * FROM rainfall_sites AS rs
        WHERE ST_Intersects(rs.geometry, ST_GeomFromText('{catchment}', 4326))"""
    sites_in_catchment = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry", crs=4326)
    # Get site locations geometry (geometry column)
    sites_geom = sites_in_catchment["geometry"]
    # Add new column 'exists' which identifies whether each site is within the catchment area
    sites_in_catchment["exists"] = sites_geom.within(catchment)
    # Filter for all sites that are within the catchment area (i.e., all Trues in 'exists' column)
    sites_in_catchment.query("exists == True", inplace=True)
    # Reset the index (i.e., the original index is added as a column, and a new sequential index is used)
    sites_in_catchment.reset_index(inplace=True)
    # Rename column
    sites_in_catchment.rename(columns={"index": "order"}, inplace=True)
    return sites_in_catchment


def main():
    engine = setup_environment.get_database()
    sites = get_rainfall_sites_data()
    rainfall_sites_to_db(engine, sites)


if __name__ == "__main__":
    main()
