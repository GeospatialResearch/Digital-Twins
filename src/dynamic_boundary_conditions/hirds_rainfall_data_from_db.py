# -*- coding: utf-8 -*-
"""
@Description: Retrieve all rainfall data for sites within the catchment area from the database.
@Author: pkh35, sli229
"""

import logging
from typing import Optional

import geopandas as gpd
import pandas as pd
from sqlalchemy.engine import Engine

from src.dynamic_boundary_conditions import hirds_rainfall_data_to_db

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def filter_for_duration(rain_data: pd.DataFrame, duration: str) -> pd.DataFrame:
    """
    Filter the HIRDS rainfall data for a requested duration.

    Parameters
    ----------
    rain_data : pd.DataFrame
        HIRDS rainfall data in Pandas DataFrame format.
    duration : str
        Storm duration. Valid options are: '10m', '20m', '30m', '1h', '2h', '6h', '12h', '24h', '48h', '72h',
        '96h', '120h', or 'all'.

    Returns
    -------
    pd.DataFrame
        Filtered rainfall data for the requested duration.
    """
    if duration != "all":
        # Filter the rain_data DataFrame to include only the relevant columns for the requested duration
        rain_data = rain_data[["site_id", "category", "rcp", "time_period", "ari", "aep", duration]]
    return rain_data


def get_each_site_rainfall_data(
        engine: Engine,
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
    engine : Engine
        The engine used to connect to the database.
    site_id : str
        HIRDS rainfall site ID.
    rcp : Optional[float]
        Representative Concentration Pathway (RCP) value. Valid options are 2.6, 4.5, 6.0, 8.5, or None
        for historical data.
    time_period : Optional[str]
        Future time period. Valid options are "2031-2050", "2081-2100", or None for historical data.
    ari : float
        Average Recurrence Interval (ARI) value. Valid options are 1.58, 2, 5, 10, 20, 30, 40, 50, 60, 80, 100, or 250.
    duration : str
        Storm duration. Valid options are: '10m', '20m', '30m', '1h', '2h', '6h', '12h', '24h', '48h', '72h',
        '96h', '120h', or 'all'.
    idf : bool
        Set to False for rainfall depth data, and True for rainfall intensity data.

    Returns
    -------
    pd.DataFrame
        HIRDS rainfall data for the requested site and parameters.

    Raises
    ------
    ValueError
        If rcp and time_period arguments are inconsistent.
    """
    # Get the relevant rainfall data table name from the idf parameter
    rain_table_name = hirds_rainfall_data_to_db.db_rain_table_name(idf)
    # Check for inconsistent rcp and time_period arguments
    if (rcp is None and time_period is not None) or (rcp is not None and time_period is None):
        raise ValueError("Inconsistent arguments provided. "
                         "For historical data, both 'rcp' and 'time_period' should be None. "
                         "If 'rcp' is None, 'time_period' should also be None, and vice versa.")
    elif rcp is not None and time_period is not None:
        # Query for specific rcp and time_period
        query = f"""
        SELECT *
        FROM {rain_table_name}
        WHERE site_id='{site_id}' AND rcp='{rcp}' AND time_period='{time_period}' AND ari={ari};
        """
        rain_data = pd.read_sql_query(query, engine)
    else:
        # Query for historical data (rcp is None and time_period is None)
        query = f"""
        SELECT *
        FROM {rain_table_name}
        WHERE site_id='{site_id}' AND rcp IS NULL AND time_period IS NULL AND ari={ari};
        """
        rain_data = pd.read_sql_query(query, engine)
        # Filter for historical data
        rain_data.query("category == 'hist'", inplace=True)
    # Filter for duration
    rain_data = filter_for_duration(rain_data, duration)
    return rain_data


def rainfall_data_from_db(
        engine: Engine,
        sites_in_catchment: gpd.GeoDataFrame,
        rcp: Optional[float],
        time_period: Optional[str],
        ari: float,
        idf: bool,
        duration: str = "all") -> pd.DataFrame:
    """
    Get rainfall data for the sites within the catchment area and return it as a Pandas DataFrame.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    sites_in_catchment : gpd.GeoDataFrame
        Rainfall sites coverage areas (Thiessen polygons) within the catchment area.
    rcp : Optional[float]
        Representative Concentration Pathway (RCP) value. Valid options are 2.6, 4.5, 6.0, 8.5, or None
        for historical data.
    time_period : Optional[str]
        Future time period. Valid options are "2031-2050", "2081-2100", or None for historical data.
    ari : float
        Average Recurrence Interval (ARI) value. Valid options are 1.58, 2, 5, 10, 20, 30, 40, 50, 60, 80, 100, or 250.
    idf : bool
        Set to False for rainfall depth data, and True for rainfall intensity data.
    duration : str, optional
        Storm duration. Valid options are: '10m', '20m', '30m', '1h', '2h', '6h', '12h', '24h', '48h', '72h',
        '96h', '120h', or 'all'. Default is 'all'.

    Returns
    -------
    pd.DataFrame
        A DataFrame containing the rainfall data for the sites within the catchment area.
    """
    # Get the site IDs within the catchment area
    sites_id_in_catchment = hirds_rainfall_data_to_db.get_sites_id_in_catchment(sites_in_catchment)
    # Initialize an empty DataFrame to store the rainfall data
    rain_data_in_catchment = pd.DataFrame()
    # Iterate over each site ID in the catchment area
    for site_id in sites_id_in_catchment:
        # Retrieve the rainfall data for each site
        rain_data = get_each_site_rainfall_data(engine, site_id, rcp, time_period, ari, duration, idf)
        # Concatenate the site's rainfall data to the overall catchment data
        rain_data_in_catchment = pd.concat([rain_data_in_catchment, rain_data], ignore_index=True)
    return rain_data_in_catchment
