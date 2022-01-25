# -*- coding: utf-8 -*-
"""
Created on Thu Jan 20 16:36:59 2022.

@author: pkh35
"""

import sys
import pandas as pd
import geopandas
from src.dynamic_boundary_conditions import hirds_depth_data_to_db


def catchment_area_geometry_info(file):
    """Extract geometry from the shape file, returns polygon."""
    catchment = geopandas.read_file(file)
    catchment = catchment.to_crs(4326)
    catchment_area = catchment.geometry[0]
    return catchment_area


def get_each_site_hirds_depth_data(ari, duration, site, engine, rcp=None, time_period=None):
    """Get hirds rainfall depth data from the database."""
    if rcp is None and time_period is not None or rcp is not None and time_period is None:
        print("check the arguments of get_hirds_depth_data\n if rcp is None,time period should be None and vice-versa")
        sys.exit()
    else:
        if rcp is not None and time_period is not None:
            query = f"""select site_id, "{duration}h" from hirds_rain_depth where site_id='{site}' and ari={ari} and\
                rcp='{rcp}' and time_period='{time_period}'"""
        else:
            query = f"""select site_id, "{duration}h" from hirds_rain_depth where site_id='{site}' and ari={ari} and\
                rcp is null and time_period is null"""
        rain_depth = engine.execute(query)
        rain_depth = list(rain_depth.fetchone())
        print(rain_depth)
        return rain_depth


def hirds_depths_from_db(engine, catchment_area, path, ari, duration, rcp=None, time_period=None):
    """Get the list of depths and site's id of each sites and return in the dataframe format."""
    sites_in_catchment = hirds_depth_data_to_db.get_sites_in_catchment(catchment_area, engine)

    depths_list = []
    for site_id in sites_in_catchment:
        rain_depth = get_each_site_hirds_depth_data(ari, duration, site_id, engine, rcp=None, time_period=None)
        depths_list.append(rain_depth)
    rain_depth_data = pd.DataFrame((depths_list), columns=['site_id', 'depth'])
    return rain_depth_data
