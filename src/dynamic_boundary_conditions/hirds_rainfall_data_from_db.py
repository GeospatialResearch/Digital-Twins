# -*- coding: utf-8 -*-
"""
@Script name: hirds_rainfall_data_from_db.py
@Description: Get all the rainfall data for the sites within the catchment area from the database.
@Author: pkh35
@Date: 20/01/2022
@Last modified by: sli229
@Last modified date: 8/11/2022
"""

import pandas as pd
import pathlib
import logging
import sys
from typing import Optional
from shapely.geometry import Polygon
from src.digitaltwin import setup_environment
from src.dynamic_boundary_conditions import main_rainfall
from src.dynamic_boundary_conditions import hirds_rainfall_data_to_db

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
        engine, site_id: str,
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
        log.error(
            "Check the arguments of the 'rainfall_data_from_db' function. "
            "If rcp is None, time period should be None, and vice-versa.")
        sys.exit()
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
        catchment_polygon: Polygon,
        rcp: Optional[float],
        time_period: Optional[str],
        ari: float,
        duration: str,
        idf: bool) -> pd.DataFrame:
    """
    Get all the rainfall data for the sites within the catchment area and return the required data in
    Pandas DataFrame format.

    Parameters
    ----------
    engine
        Engine used to connect to the database.
    catchment_polygon : Polygon
        Desired catchment area.
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
    sites_id_in_catchment = hirds_rainfall_data_to_db.get_sites_id_in_catchment(engine, catchment_polygon)

    rain_data_in_catchment = pd.DataFrame()
    for site_id in sites_id_in_catchment:
        rain_data = get_each_site_rainfall_data(engine, site_id, rcp, time_period, ari, duration, idf)
        rain_data_in_catchment = pd.concat([rain_data_in_catchment, rain_data], ignore_index=True)
    return rain_data_in_catchment


def main():
    catchment_file = pathlib.Path(r"src\dynamic_boundary_conditions\catchment_polygon.shp")
    rcp = 2.6
    time_period = "2031-2050"
    ari = 100
    # To get rainfall data for all durations set duration to "all"
    duration = "all"
    engine = setup_environment.get_database()
    catchment_polygon = main_rainfall.catchment_area_geometry_info(catchment_file)
    # Set idf to False for rain depth data and to True for rain intensity data
    rain_depth_in_catchment = rainfall_data_from_db(
        engine, catchment_polygon, rcp, time_period, ari, duration, idf=False)
    print(rain_depth_in_catchment)
    rain_intensity_in_catchment = rainfall_data_from_db(
        engine, catchment_polygon, rcp, time_period, ari, duration, idf=True)
    print(rain_intensity_in_catchment)


if __name__ == "__main__":
    main()
