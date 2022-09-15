# -*- coding: utf-8 -*-
"""
Created on Mon Jan 17 09:32:16 2022.

@author: pkh35
"""

import numpy
import pandas as pd
import geopandas as gpd
import pathlib
import shapely.geometry
from src.digitaltwin import setup_environment
from src.dynamic_boundary_conditions import rainfall_sites
from src.dynamic_boundary_conditions import thiessen_polygon_calculator
from src.dynamic_boundary_conditions import hirds_depth_data_to_db
from src.dynamic_boundary_conditions import hirds_depth_data_from_db


def hyetograph(duration, site, total_rain_depth):
    """Take inputs from the database to create a design storm."""
    # TODO: is this the chicago method? how are these numbers derived? formula for this?
    #  don't quite understand how to derive hyetographs.
    # m is the ordinate of (proportion of rain fallen at) the peak rainfall depth
    m = 0.53
    # n is the abscissa of (proportion of time past at) the peak rainfall depth
    n = 0.55
    # wl and wr are warp or shape factors left and right of the point of contraflexure or peak rainfall depth
    wl = 4.00
    wr = 4.61
    R = total_rain_depth
    N = duration
    time_list = []
    prcp_list = []
    for t in range(N + 1):
        dt = t / N  # dt is the proportion of the duration
        if dt <= n:
            x = (((t) / N) - n) * wl
        else:
            x = (((t) / N) - n) * wr
        tan = numpy.tanh(x)
        s = (m * tan) + m
        pt = R * s  # Pt is the proportion of total rainfall depth of a hyetograph
        # TODO: accumulated total rainfall depth ^ (above line)???
        pt = round(pt, 2)
        duration, proportion_rain = t, pt
        time_list.append(duration)
        prcp_list.append(proportion_rain)
    hyetograph_data = pd.DataFrame({'time': time_list, 'prcp': prcp_list})
    del time_list, prcp_list
    hyetograph_data['prcp_prop'] = hyetograph_data['prcp'].diff()
    # prcp_prop is the proportion of the total rainfall.
    # TODO: total rainfall depth each hour???
    hyetograph_data['prcp_prop'] = hyetograph_data['prcp_prop'].fillna(0)
    return hyetograph_data


def catchment_area_geometry_info(catchment_file) -> shapely.geometry.Polygon:
    """Extract shapely polygon geometry from the catchment file"""
    catchment = gpd.read_file(catchment_file)
    catchment = catchment.to_crs(4326)
    catchment_polygon = catchment["geometry"][0]
    return catchment_polygon


def main():
    catchment_file = pathlib.Path(
        r"C:\Users\sli229\Projects\Digital-Twins\src\dynamic_boundary_conditions\catchment_polygon.shp")
    file_path_to_store = pathlib.Path(r"U:\Research\FloodRiskResearch\DigitalTwin\hirds_rainfall_data")
    rcp = 2.6
    time_period = "2031-2050"
    ari = 100
    duration = "24h"

    engine = setup_environment.get_database()
    sites = rainfall_sites.get_rainfall_sites_data()
    rainfall_sites.rainfall_sites_to_db(engine, sites)
    nz_boundary = rainfall_sites.get_new_zealand_boundary(engine)
    sites_in_catchment = rainfall_sites.get_sites_locations(engine, nz_boundary)
    thiessen_polygon_calculator.thiessen_polygons(engine, nz_boundary, sites_in_catchment)
    catchment_polygon = catchment_area_geometry_info(catchment_file)
    hirds_depth_data_to_db.rain_depths_to_db(engine, catchment_polygon, file_path_to_store)
    rain_depth_in_catchment = hirds_depth_data_from_db.rain_depths_from_db(
        engine, catchment_polygon, rcp, time_period, ari, duration)

    # for site_id, depth in zip(rain_depth_in_catchment.site_id, rain_depth_in_catchment.depth):
    #     hyt = hyetograph(duration, site_id, depth)
    #     hyt.plot.bar(title=f'{ari}-year storm: site {site_id}', x='time', y='prcp_prop', rot=0)
    #     # TODO: hyetograph data table is input into BG-Flood model


if __name__ == "__main__":
    main()
