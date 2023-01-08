# -*- coding: utf-8 -*-
"""
@Script name: hirds_rainfall_data_from_db.py
@Description: Get all rainfall data for sites within the catchment area from the database.
@Author: pkh35
@Date: 20/01/2022
@Last modified by: sli229
@Last modified date: 5/12/2022
"""

import logging
import pathlib
from typing import Optional

import geopandas as gpd
import pandas as pd

from src.digitaltwin import setup_environment
from src.dynamic_boundary_conditions import main_rainfall, thiessen_polygons, hirds_rainfall_data_to_db

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def filter_for_duration(rain_data: pd.DataFrame, duration: str) -> pd.DataFrame:
    """
    Used to filter the HIRDS rainfall data for a requested duration.

    Parameters
    ----------
    rain_data : pd.DataFrame
        HIRDS rainfall data in Pandas Dataframe format.
    duration : str
        Storm duration, i.e. 10m, 20m, 30m, 1h, 2h, 6h, 12h, 24h, 48h, 72h, 96h, 120h, or 'all'.
    """
    if duration != "all":
        rain_data = rain_data[["site_id", "category", "rcp", "time_period", "ari", "aep", duration]]
    return rain_data


def get_each_site_rainfall_data(
        engine,
        site_id: str,
        rcp: Optional[float],
        time_period: Optional[str],
        ari: float,
        duration: str,
        idf: bool) -> pd.DataFrame:
    """
    Get the HIRDS rainfall data for the requested site from the database and return the required data in
    Pandas DataFrame format.


    Parameters
    ----------
    engine
        Engine used to connect to the database.
    site_id : str
        HIRDS rainfall site id.
    rcp : Optional[float]
        There are four different representative concentration pathways (RCPs), and abbreviated as RCP2.6, RCP4.5,
        RCP6.0 and RCP8.5, in order of increasing radiative forcing by greenhouse gases, or None for historical data.
    time_period : Optional[str]
        Rainfall estimates for two future time periods (e.g. 2031-2050 or 2081-2100) for four RCPs, or None for
        historical data.
    ari : float
        Storm average recurrence interval (ARI), i.e. 1.58, 2, 5, 10, 20, 30, 40, 50, 60, 80, 100, or 250.
    duration : str
        Storm duration, i.e. 10m, 20m, 30m, 1h, 2h, 6h, 12h, 24h, 48h, 72h, 96h, 120h, or 'all'.
    idf : bool
        Set to False for rainfall depth data, and True for rainfall intensity data.
    """
    rain_table_name = hirds_rainfall_data_to_db.db_rain_table_name(idf)
    if (rcp is None and time_period is not None) or (rcp is not None and time_period is None):
        raise ValueError("Check the arguments of the 'rainfall_data_from_db' function. "
                         "If rcp is None, time period should be None, and vice-versa.")
    elif rcp is not None and time_period is not None:
        query = f"""SELECT * FROM {rain_table_name}
        WHERE site_id='{site_id}' AND rcp='{rcp}' AND time_period='{time_period}' AND ari={ari};"""
        rain_data = pd.read_sql_query(query, engine)
    else:
        query = f"""SELECT * FROM {rain_table_name}
        WHERE site_id='{site_id}' AND rcp IS NULL AND time_period IS NULL AND ari={ari};"""
        rain_data = pd.read_sql_query(query, engine)
        # filter for historical data
        rain_data.query("category == 'hist'", inplace=True)
    # filter for duration
    rain_data = filter_for_duration(rain_data, duration)
    return rain_data


def rainfall_data_from_db(
        engine,
        sites_in_catchment: gpd.GeoDataFrame,
        rcp: Optional[float],
        time_period: Optional[str],
        ari: float,
        idf: bool,
        duration: str = "all") -> pd.DataFrame:
    """
    Get all the rainfall data for the sites within the catchment area and return the required data in
    Pandas DataFrame format.

    Parameters
    ----------
    engine
        Engine used to connect to the database.
    sites_in_catchment : gpd.GeoDataFrame
        Rainfall sites coverage areas (thiessen polygons) that are within the catchment area.
    rcp : Optional[float]
        There are four different representative concentration pathways (RCPs), and abbreviated as RCP2.6, RCP4.5,
        RCP6.0 and RCP8.5, in order of increasing radiative forcing by greenhouse gases, or None for historical data.
    time_period : Optional[str]
        Rainfall estimates for two future time periods (e.g. 2031-2050 or 2081-2100) for four RCPs, or None for
        historical data.
    ari : float
        Storm average recurrence interval (ARI), i.e. 1.58, 2, 5, 10, 20, 30, 40, 50, 60, 80, 100, or 250.
    idf : bool
        Set to False for rainfall depth data, and True for rainfall intensity data.
    duration : str
        Storm duration, i.e. 10m, 20m, 30m, 1h, 2h, 6h, 12h, 24h, 48h, 72h, 96h, 120h, or 'all'.
    """
    sites_id_in_catchment = hirds_rainfall_data_to_db.get_sites_id_in_catchment(sites_in_catchment)

    rain_data_in_catchment = pd.DataFrame()
    for site_id in sites_id_in_catchment:
        rain_data = get_each_site_rainfall_data(engine, site_id, rcp, time_period, ari, duration, idf)
        rain_data_in_catchment = pd.concat([rain_data_in_catchment, rain_data], ignore_index=True)
    return rain_data_in_catchment


def main():
    # Catchment polygon
    catchment_file = pathlib.Path(r"selected_polygon.geojson")
    catchment_polygon = main_rainfall.catchment_area_geometry_info(catchment_file)
    # Connect to the database
    engine = setup_environment.get_database()
    # Get all rainfall sites (thiessen polygons) coverage areas that are within the catchment area
    sites_in_catchment = thiessen_polygons.thiessen_polygons_from_db(engine, catchment_polygon)
    # Requested scenario
    rcp = 2.6
    time_period = "2031-2050"
    ari = 100
    # For a requested scenario, get all rainfall data for sites within the catchment area from the database
    # Set idf to False for rain depth data and to True for rain intensity data
    rain_depth_in_catchment = rainfall_data_from_db(engine, sites_in_catchment, rcp, time_period, ari, idf=False)
    print(rain_depth_in_catchment)
    rain_intensity_in_catchment = rainfall_data_from_db(engine, sites_in_catchment, rcp, time_period, ari, idf=True)
    print(rain_intensity_in_catchment)


if __name__ == "__main__":
    main()
