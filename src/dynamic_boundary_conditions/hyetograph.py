# -*- coding: utf-8 -*-
"""
Created on Mon Jan 17 09:32:16 2022.

@author: pkh35
"""

import numpy
import pandas as pd
from src.digitaltwin import setup_environment
from src.dynamic_boundary_conditions import hirds_data_to_db_version2
engine = setup_environment.get_database()


def hyetograph(ari, duration, site, rain_depth):
    """Take inputs from the database to create a design storm."""
    # m and n are the ordinate of (proportion of rain fallen at) and abscissa of (propotion of time past at) the peak rainfall depth
    m = 0.53
    n = 0.55
    wl = 4.00
    wr = 4.61
    R = rain_depth
    N = duration
    time_list = []
    prcp_list = []
    for t in range(N+1):
        Dt = t/N
        if Dt <= n:
            x = (((t)/N)-n)*wl
        else:
            x = (((t)/N)-n)*wr
        tan = numpy.tanh(x)
        s = (m*tan)+m
        Rt = R*s
        Rt = "{:.2f}".format(Rt)
        a, b = t,  Rt
        time_list.append(a)
        prcp_list.append(b)
    df = pd.DataFrame({'time': time_list, 'prcp': prcp_list})
    del time_list, prcp_list
    df = df.astype({"time": int, "prcp": float})
    df['prcp_prop'] = df['prcp'].diff()
    df['prcp_prop'] = df['prcp_prop'].fillna(0)
    return df


if __name__ == "__main__":
    engine = setup_environment.get_database()
    file = r'P:\Data\catch5.shp'
    path = r"\\file\Research\FloodRiskResearch\DigitalTwin\hirds_depth_data"
    ari = 100
    duration = 24
    rcp = "2.6"
    time_period = "2031-2050"
    depths_data = hirds_data_to_db_version2.hirds_depths_from_db(engine, file, path, ari, duration, rcp, time_period)
    for site_id, depth in zip(depths_data.site_id, depths_data.depth):
        hyt = hyetograph(ari, duration, site_id, depth)
        hyt.plot.bar(x='time', y='prcp_prop', rot=0)
