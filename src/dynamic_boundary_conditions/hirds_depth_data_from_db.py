# -*- coding: utf-8 -*-
"""
Created on Thu Jan 20 16:36:59 2022.

@author: pkh35
"""

import pandas as pd
import pathlib
import logging
import sys
from shapely.geometry import Polygon
from src.dynamic_boundary_conditions import hirds_depth_data_to_db
from src.digitaltwin import setup_environment
from src.dynamic_boundary_conditions import hyetograph

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def filter_for_duration(rain_depth: pd.DataFrame, duration: str):
    if duration is not None:
        rain_depth = rain_depth[["site_id", "rcp", "time_period", "ari", "aep", f"{duration}"]]
    return rain_depth


def get_each_site_rain_depth_data(
        engine, site_id: str, rcp: float, time_period: str, ari: float, duration: str) -> pd.DataFrame:
    """Get the hirds rainfall depth data for the requested site from the database and return in dataframe format."""
    if (rcp is None and time_period is not None) or (rcp is not None and time_period is None):
        log.error(
            "Check the arguments of the 'rain_depths_from_db' function. "
            "If rcp is None, time period should be None, and vice-versa.")
        sys.exit()
    elif rcp is not None and time_period is not None:
        query = f"""SELECT * FROM rainfall_depth
        WHERE site_id='{site_id}' AND rcp='{rcp}' AND time_period='{time_period}' AND ari={ari};"""
        rain_depth = pd.read_sql_query(query, engine)
    else:
        query = f"""SELECT * FROM rainfall_depth
        WHERE site_id='{site_id}' AND rcp IS NULL AND time_period IS NULL AND ari={ari};"""
        rain_depth = pd.read_sql_query(query, engine).head(1)
    rain_depth = filter_for_duration(rain_depth, duration)
    return rain_depth


def rain_depths_from_db(
        engine, catchment_polygon: Polygon, rcp: float, time_period: str, ari: float, duration: str) -> pd.DataFrame:
    """Get all the rainfall depth data for the sites within the catchment area and return in dataframe format."""
    sites_id_in_catchment = hirds_depth_data_to_db.get_sites_id_in_catchment(catchment_polygon, engine)

    rain_depth_in_catchment = pd.DataFrame()
    for site_id in sites_id_in_catchment:
        rain_depth = get_each_site_rain_depth_data(engine, site_id, rcp, time_period, ari, duration)
        rain_depth_in_catchment = pd.concat([rain_depth_in_catchment, rain_depth], ignore_index=True)
    return rain_depth_in_catchment


def main():
    catchment_file = pathlib.Path(
        r"C:\Users\sli229\Projects\Digital-Twins\src\dynamic_boundary_conditions\catchment_polygon.shp")
    rcp = 2.6
    time_period = "2031-2050"
    ari = 100
    # To get rainfall depths data for all durations set duration to None
    duration = None
    engine = setup_environment.get_database()
    catchment_polygon = hyetograph.catchment_area_geometry_info(catchment_file)
    rain_depth_in_catchment = rain_depths_from_db(engine, catchment_polygon, rcp, time_period, ari, duration)
    print(rain_depth_in_catchment)


if __name__ == "__main__":
    main()
