# -*- coding: utf-8 -*-
"""
Created on Mon Jan 17 09:32:16 2022.

@author: pkh35
"""

import numpy
import pandas as pd
from src.digitaltwin import setup_environment
from src.dynamic_boundary_conditions import hirds_depth_data_from_db
from src.dynamic_boundary_conditions import hirds_depth_data_to_db


def hyetograph(ari, duration, site, total_rain_depth):
    """Take inputs from the database to create a design storm."""
    # m and n are the ordinate of (proportion of rain fallen at) and abscissa of (propotion of time past at) the peak rainfall depth
    m = 0.53
    n = 0.55
    #wl and wr are warp or shape factors left and right of the point of contraflexure or peak rainfall depth
    wl = 4.00
    wr = 4.61
    R = total_rain_depth
    N = duration
    time_list = []
    prcp_list = []
    for t in range(N+1):
        Dt = t/N  # Dt is the proportion of the duration
        if Dt <= n:
            x = (((t)/N)-n)*wl
        else:
            x = (((t)/N)-n)*wr
        tan = numpy.tanh(x)
        s = (m*tan)+m
        Pt = R*s  # Pt is the proportion of total rainfall depth of a hyetograph,
        Pt = "{:.2f}".format(Pt)
        duration, proportion_rain = t, Pt
        time_list.append(duration)
        prcp_list.append(proportion_rain)
    df = pd.DataFrame({'time': time_list, 'prcp': prcp_list})
    del time_list, prcp_list
    df = df.astype({"time": int, "prcp": float})
    df['prcp_prop'] = df['prcp'].diff()
    df['prcp_prop'] = df['prcp_prop'].fillna(0)
    return df


if __name__ == "__main__":
    engine = setup_environment.get_database()
    file = r'P:\Data\catch5.shp'
    path = r'\\file\Research\FloodRiskResearch\DigitalTwin\hirds_depth_data'
    ari = 100
    duration = 24
    rcp = "2.6"
    time_period = "2031-2050"
    catchment_area = hirds_depth_data_from_db.catchment_area_geometry_info(file)
    hirds_depth_data_to_db.hirds_depths_to_db(engine, catchment_area, path)
    depths_data = hirds_depth_data_from_db.hirds_depths_from_db(engine, catchment_area, path, ari, duration, rcp, time_period)
    print(depths_data)
    for site_id, depth in zip(depths_data.site_id, depths_data.depth):
        hyt = hyetograph(ari, duration, site_id, depth)
        hyt.plot.bar(x='time', y='prcp_prop', rot=0)
