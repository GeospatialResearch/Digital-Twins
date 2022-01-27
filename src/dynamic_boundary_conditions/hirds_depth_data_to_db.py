# -*- coding: utf-8 -*-
"""
Created on Thu Jan 20 15:09:11 2022

@author: pkh35
"""

import pandas as pd
import geopandas
import numpy as np
import sqlalchemy
from shapely.geometry import Polygon
from src.dynamic_boundary_conditions import rain_depth_data_from_hirds


def check_table_exists(engine):
    """Check if the region_geometry table exists in the database."""
    insp = sqlalchemy.inspect(engine)
    return insp.has_table("hirds_rain_depth", schema="public")


def get_sites_in_catchment(catchment_area: Polygon, engine):
    """Get gauges within the catchment area from the database."""
    query = f'''select site_id from public.hirds_gauges f
        where ST_Intersects(f.geometry, ST_GeomFromText('{catchment_area}', 4326))'''
    gauges_in_catchment = pd.read_sql_query(query, engine)
    return gauges_in_catchment['site_id'].tolist()


def get_sites_not_in_db(engine, sites_in_catchment):
    """To only get the data for the sites for which data are not avialble in the database."""
    query = "select distinct site_id from hirds_rain_depth"
    gauges = engine.execute(query)
    sites = gauges.fetchall()
    sites = list(sites)
    sites_in_db = []
    for i in range(len(sites)):
        sites_in_db.append(sites[i][0])
    # yields the elements in `sites_in_catchment` that are NOT in `sites_in_db`
    sites = np.setdiff1d(sites_in_catchment, sites_in_db)
    return sites


def get_data_from_csv(filename: str, site_id: str, rcp, time_period, n: int):
    """Read data of the diffrent time period and return a dataframe."""
    hirds_data = pd.read_csv(filename, skiprows=n, nrows=12, index_col=None, quotechar='"')
    hirds_data['site_id'] = site_id
    hirds_data['rcp'] = rcp
    hirds_data['time_period'] = time_period
    hirds_data.columns = hirds_data.columns.str.lower()
    return hirds_data


def add_hirds_depth_data_to_db(path: str, site_id: str, engine):
    """Store each site's depth data in the database.

    each csv file file conatins data for historical rainfall depth, and for various rcp and time period.
    To view the csv file, go to : https://hirds.niwa.co.nz/, select a site and generate a report,
    there are rainfall depths for diffrent RCP Scenarios.
    To understand the structure of the CSV file, download the spreadsheet.
    """
    the_values = [(None, None, 12),
                  (2.6, '2031-2050', 40),
                  (2.6, '2081-2100', 54),
                  (4.5, '2031-2050', 68),
                  (4.5, '2081-2100', 82),
                  (6, '2031-2050', 96),
                  (6, '2081-2100', 110),
                  (8.5, '2031-2050', 124),
                  (8.5, '2081-2100', 138)]
    filename = fr'{path}\{site_id}_depth.csv'
    print("Adding data for site", site_id)
    for (rcp, time_period, n) in the_values:
        site_data = get_data_from_csv(filename, site_id, rcp=rcp, time_period=time_period, n=n)
        site_data.to_sql('hirds_rain_depth', engine, index=False, if_exists='append')


def hirds_depths_to_db(engine, catchment_area: Polygon, path):
    """Store depth data of all the sites within the catchment area in the database."""
    sites_in_catchment = get_sites_in_catchment(catchment_area, engine)
    if check_table_exists(engine):
        site_ids = get_sites_not_in_db(engine, sites_in_catchment)
        if site_ids != 0:
            for site_id in site_ids:
                rain_depth_data_from_hirds.get_data_from_hirds(site_id, path)
                add_hirds_depth_data_to_db(path, site_id, engine)
        else:
            print("sites for the requested catchment available in the database.")
    else:
        site_ids = sites_in_catchment
        if site_ids != 0:
            for site_id in site_ids:
                rain_depth_data_from_hirds.get_data_from_hirds(site_id, path)
                add_hirds_depth_data_to_db(path, site_id, engine)
        else:
            print("There are no sites within the requested catchment area, select a wider area")


if __name__ == "__main__":
    from src.digitaltwin import setup_environment
    engine = setup_environment.get_database()
    file = r'P:\Data\catch4.shp'
    path = r'\\file\Research\FloodRiskResearch\DigitalTwin\hirds_depth_data'
    catchment = geopandas.read_file(file)
    catchment = catchment.to_crs(4326)
    catchment_area = catchment.geometry[0]
    hirds_depths_to_db(engine, catchment_area, path)
