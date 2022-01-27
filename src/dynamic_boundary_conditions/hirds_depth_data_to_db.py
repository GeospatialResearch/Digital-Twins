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
    table_exist = insp.has_table("hirds_rain_depth", schema="public")
    return table_exist


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
    """Store each site's depth data in the database."""
    filename = fr'{path}\{site_id}_depth.csv'
    site_data = get_data_from_csv(filename, site_id, rcp=None, time_period=None, n=12)
    site_data.to_sql('hirds_rain_depth', engine, index=False, if_exists='append')
    site_data = get_data_from_csv(filename, site_id, rcp=2.6, time_period='2031-2050', n=40)
    site_data.to_sql('hirds_rain_depth', engine, index=False, if_exists='append')
    site_data = get_data_from_csv(filename, site_id, rcp=2.6, time_period='2081-2100', n=54)
    site_data.to_sql('hirds_rain_depth', engine, index=False, if_exists='append')
    site_data = get_data_from_csv(filename, site_id, rcp=4.5, time_period='2031-2050', n=68)
    site_data.to_sql('hirds_rain_depth', engine, index=False, if_exists='append')
    site_data = get_data_from_csv(filename, site_id, rcp=4.5, time_period='2081-2100', n=82)
    site_data.to_sql('hirds_rain_depth', engine, index=False, if_exists='append')
    site_data = get_data_from_csv(filename, site_id, rcp=6, time_period='2031-2050', n=96)
    site_data.to_sql('hirds_rain_depth', engine, index=False, if_exists='append')
    site_data = get_data_from_csv(filename, site_id, rcp=6, time_period='2081-2100', n=110)
    site_data.to_sql('hirds_rain_depth', engine, index=False, if_exists='append')
    site_data = get_data_from_csv(filename, site_id, rcp=8.5, time_period='2031-2050', n=124)
    site_data.to_sql('hirds_rain_depth', engine, index=False, if_exists='append')
    site_data = get_data_from_csv(filename, site_id, rcp=8.5, time_period='2081-2100', n=138)
    site_data.to_sql('hirds_rain_depth', engine, index=False, if_exists='append')


def hirds_depths_to_db(engine, catchment_area: Polygon, path):
    """Store depth data of all the sites within the catchment area in the database."""
    table_exits = check_table_exists(engine)
    sites_in_catchment = get_sites_in_catchment(catchment_area, engine)
    if table_exits is True:
        sites_not_in_db = get_sites_not_in_db(engine, sites_in_catchment)
        site_ids = sites_not_in_db
        if site_ids.size != 0:
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
    file = r'P:\Data\catch5.shp'
    path = r'\\file\Research\FloodRiskResearch\DigitalTwin\hirds_depth_data'
    catchment = geopandas.read_file(file)
    catchment = catchment.to_crs(4326)
    catchment_area = catchment.geometry[0]
    hirds_depths_to_db(engine, catchment_area, path)
