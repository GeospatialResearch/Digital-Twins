# -*- coding: utf-8 -*-
"""
Created on Mon Jan 17 09:32:16 2022.

@author: pkh35
"""

import numpy
import pandas as pd


def hyetograph(duration, site, total_rain_depth):
    """Take inputs from the database to create a design storm."""
    # m is the ordinate of (proportion of rain fallen at) the peak rainfall depth
    m = 0.53
    # n is the abscissa of (propotion of time past at) the peak rainfall depth
    n = 0.55
    # wl and wr are warp or shape factors left and right of the point of contraflexure or peak rainfall depth
    wl = 4.00
    wr = 4.61
    R = total_rain_depth
    N = duration
    time_list = []
    prcp_list = []
    for t in range(N+1):
        dt = t/N  # dt is the proportion of the duration
        if dt <= n:
            x = (((t)/N)-n)*wl
        else:
            x = (((t)/N)-n)*wr
        tan = numpy.tanh(x)
        s = (m*tan)+m
        pt = R*s  # Pt is the proportion of total rainfall depth of a hyetograph,
        pt = "{:.2f}".format(pt)
        duration, proportion_rain = t, pt
        time_list.append(duration)
        prcp_list.append(proportion_rain)
    hyetograph_data = pd.DataFrame({'time': time_list, 'prcp': prcp_list})
    del time_list, prcp_list
    hyetograph_data = hyetograph_data.astype({"time": int, "prcp": float})
    hyetograph_data['prcp_prop'] = hyetograph_data['prcp'].diff()
    # prcp_prop is the proportion of the total rainfall.
    hyetograph_data['prcp_prop'] = hyetograph_data['prcp_prop'].fillna(0)
    return hyetograph_data


if __name__ == "__main__":
    from src.digitaltwin import setup_environment
    from src.dynamic_boundary_conditions import hirds_gauges
    from src.dynamic_boundary_conditions import theissen_polygon_calculator
    from src.dynamic_boundary_conditions import hirds_depth_data_to_db
    from src.dynamic_boundary_conditions import hirds_depth_data_from_db
    engine = setup_environment.get_database()
    file = r'P:\Data\catch5.shp'
    path = r'\\file\Research\FloodRiskResearch\DigitalTwin\hirds_depth_data'
    ari = 100
    duration = 24
    rcp = "2.6"
    time_period = "2031-2050"
    guages = hirds_gauges.get_hirds_gauges_data()
    hirds_gauges.hirds_gauges_to_db(engine, guages)
    catchment = hirds_gauges.get_new_zealand_boundary(engine)
    gauges_in_polygon = hirds_gauges.get_gauges_location(engine, catchment)
    theissen_polygon_calculator.theissen_polygons(engine, catchment, gauges_in_polygon)
    catchment_area = hirds_depth_data_from_db.catchment_area_geometry_info(file)
    hirds_depth_data_to_db.hirds_depths_to_db(engine, catchment_area, path)
    depths_data = hirds_depth_data_from_db.hirds_depths_from_db(engine, catchment_area, ari, duration, rcp,
                                                                time_period)
    for site_id, depth in zip(depths_data.site_id, depths_data.depth):
        hyt = hyetograph(duration, site_id, depth)
        hyt.plot.bar(x='time', y='prcp_prop', rot=0)
