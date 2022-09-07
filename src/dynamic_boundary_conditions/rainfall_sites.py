# -*- coding: utf-8 -*-
"""
Created on Thu Dec 23 16:06:53 2021.

@author: pkh35
"""

import requests
from requests.structures import CaseInsensitiveDict
import pandas as pd
from shapely.geometry import Point
import geopandas as gpd
import sqlalchemy
from geoalchemy2 import Geometry
import geopandas
import numpy as np


def get_hirds_gauges_data() -> geopandas.GeoDataFrame:
    """Get rainfall sites data from the hirds website using HTTP request."""
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


def hirds_gauges_to_db(engine, hirds_gauges: geopandas.GeoDataFrame):
    """Get gauges information from the hirds website and store it in the database."""
    if not sqlalchemy.inspect(engine).has_table("hirds_gauges"):
        print("Storing gauges data from hirds in the database.")
        hirds_gauges.to_postgis('hirds_gauges', engine, if_exists='replace',
                                index=False, dtype={'geometry': Geometry(geometry_type='POINT', srid=4326)})
    else:
        print("hirds gauges information exists in the database.")


def get_new_zealand_boundary(engine) -> geopandas.GeoDataFrame:
    """Get the boundary information of new Zealand from region_geometry table."""
    query1 = "select geometry as geom from region_geometry where regc2021_v1_00_name='New Zealand'"
    catchment = geopandas.GeoDataFrame.from_postgis(query1, engine)
    catchment = catchment.to_crs(4326)
    return catchment


def get_gauges_location(engine, catchment: geopandas.GeoDataFrame):
    """
    Get the gauge locations within the catchment area from the database and return in geopandas format.
    engine: to connect to the database.
    catchment: get the geopandas dataframe of the NZ catchment area.
    """
    # Get all gauges within the New Zealand catchment area.
    catchment_area = catchment.geom[0]
    query = f'''select * from public.hirds_gauges hg
        where ST_Intersects(hg.geometry, ST_GeomFromText('{catchment_area}', 4326))'''
    gauges_in_catchment = pd.read_sql_query(query, engine)

    # Convert geometry column from wkb format to EPSG:4326
    gauges_in_catchment['geometry'] = gpd.GeoSeries.from_wkb(gauges_in_catchment['geometry'])
    # Convert pandas dataframe to geopandas dataframe
    gauges_in_catchment = gpd.GeoDataFrame(gauges_in_catchment, geometry='geometry')
    # Get gauges locations (geometry column)
    gauges = gauges_in_catchment.geometry
    # Add new column 'exists' which identifies whether the gauges are within the catchment area
    gauges_in_catchment['exists'] = gauges.within(catchment_area)
    # Filter for all gauges that are within the catchment area (i.e., all Trues in 'exists' column)
    gauges_in_polygon = gauges_in_catchment[gauges_in_catchment.all(axis=1)]
    # Add new column 'order' which acts like the index column
    gauges_in_polygon['order'] = np.arange(len(gauges_in_polygon))
    return gauges_in_polygon


if __name__ == "__main__":
    from src.digitaltwin import setup_environment
    engine = setup_environment.get_database()
    guages = get_hirds_gauges_data()
    hirds_gauges_to_db(engine, guages)
