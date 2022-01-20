# -*- coding: utf-8 -*-
"""
Created on Mon Jan 17 14:12:07 2022.

@author: pkh35
"""

import sys
import requests
from requests.structures import CaseInsensitiveDict
import pandas as pd
import geopandas as gpd
from src.digitaltwin import setup_environment
import numpy as np
import sqlalchemy
from shapely.geometry import Polygon


def catchment_area_geometry_info(file):
    """Extract geometry from the shape file, returns polygon."""
    catchment = gpd.read_file(file)
    catchment = catchment.to_crs(4326)
    catchment_area = catchment.geometry[0]
    return catchment_area


def get_sites_in_catchment(catchment_area: Polygon, engine):
    """Get gauges within the catchment area from the database."""
    query = f'''select site_id from public.hirds_gauges f
        where ST_Intersects(f.geometry, ST_GeomFromText('{catchment_area}', 4326))'''
    gauges_in_catchment = pd.read_sql_query(query, engine)
    return gauges_in_catchment['site_id'].tolist()


def get_url_id(site_id):
    """Each site has a unique key that need to be inserted in the url before making an api request."""
    url = "https://api.niwa.co.nz/hirds/report"
    headers = CaseInsensitiveDict()
    headers["Connection"] = "keep-alive"
    headers["sec-ch-ua"] = '"" Not A;Brand";v="99", "Chromium";v="96", "Google Chrome";v="96""'
    headers["Accept"] = "application/json, text/plain, */*"
    headers["Content-Type"] = "application/json"
    headers["sec-ch-ua-mobile"] = "?0"
    headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"
    headers["sec-ch-ua-platform"] = '""Windows""'
    headers["Origin"] = "https://hirds.niwa.co.nz"
    headers["Sec-Fetch-Site"] = "same-site"
    headers["Sec-Fetch-Mode"] = "cors"
    headers["Sec-Fetch-Dest"] = "empty"
    headers["Referer"] = "https://hirds.niwa.co.nz/"
    headers["Accept-Language"] = "en-GB,en-US;q=0.9,en;q=0.8"
    data = f'{{"site_id":"{site_id}","idf":false}}'
    resp = requests.post(url, headers=headers, data=data)
    hirds = pd.read_json(resp.text)  # get each sites url.
    site_url = hirds['url'][0]
    start = site_url.find("/asset/") + len("/asset/")
    # get the long digits part from the url
    site_id_url = site_url[start:]
    site_id_url = site_id_url.rsplit('/')[0]
    return site_id_url


def get_data_from_hirds(site_id, filename):
    """Get data from the hirds website using curl command and store as a csv files."""
    site_id_url = get_url_id(site_id)
    url = f"https://api.niwa.co.nz/hirds/report/{site_id_url}/export"
    headers = CaseInsensitiveDict()
    headers["Connection"] = "keep-alive"
    headers["sec-ch-ua"] = '"" Not A;Brand";v="99", "Chromium";v="96", "Google Chrome";v="96""'
    headers["Accept"] = "application/json, text/plain, */*"
    headers["sec-ch-ua-mobile"] = "?0"
    headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"
    headers["sec-ch-ua-platform"] = '""Windows""'
    headers["Origin"] = "https://hirds.niwa.co.nz"
    headers["Sec-Fetch-Site"] = "same-site"
    headers["Sec-Fetch-Mode"] = "cors"
    headers["Sec-Fetch-Dest"] = "empty"
    headers["Referer"] = "https://hirds.niwa.co.nz/"
    headers["Accept-Language"] = "en-GB,en-US;q=0.9,en;q=0.8"

    response = requests.get(url, headers=headers)
    site_info = open(filename, "w")
    site_info.write(response.text)
    site_info.close()


def get_data_from_csv(filename: str, site, rcp: float, time_period: str, n: int):
    """Read data of the diffrent time period and return a dataframe."""
    hirds_data = pd.read_csv(filename, skiprows=n, nrows=12, index_col=None, quotechar='"')
    hirds_data['site_id'] = site
    hirds_data['rcp'] = rcp
    hirds_data['time_period'] = time_period
    hirds_data.columns = hirds_data.columns.str.lower()
    return hirds_data


def add_one_site_hirds_data_to_db(filename, site, engine):
    """Store site data in the database."""
    site_data = get_data_from_csv(filename, site, rcp=None, time_period=None, n=12)
    site_data.to_sql('hirds_rain_depth', engine, index=False, if_exists='append')
    site_data = get_data_from_csv(filename, site, rcp=2.6, time_period='2031-2050', n=40)
    site_data.to_sql('hirds_rain_depth', engine, index=False, if_exists='append')
    site_data = get_data_from_csv(filename, site, rcp=2.6, time_period='2081-2100', n=54)
    site_data.to_sql('hirds_rain_depth', engine, index=False, if_exists='append')
    site_data = get_data_from_csv(filename, site, rcp=4.5, time_period='2031-2050', n=68)
    site_data.to_sql('hirds_rain_depth', engine, index=False, if_exists='append')
    site_data = get_data_from_csv(filename, site, rcp=4.5, time_period='2081-2100', n=82)
    site_data.to_sql('hirds_rain_depth', engine, index=False, if_exists='append')
    site_data = get_data_from_csv(filename, site, rcp=6, time_period='2031-2050', n=96)
    site_data.to_sql('hirds_rain_depth', engine, index=False, if_exists='append')
    site_data = get_data_from_csv(filename, site, rcp=6, time_period='2081-2100', n=110)
    site_data.to_sql('hirds_rain_depth', engine, index=False, if_exists='append')
    site_data = get_data_from_csv(filename, site, rcp=8.5, time_period='2031-2050', n=124)
    site_data.to_sql('hirds_rain_depth', engine, index=False, if_exists='append')
    site_data = get_data_from_csv(filename, site, rcp=8.5, time_period='2081-2100', n=138)
    site_data.to_sql('hirds_rain_depth', engine, index=False, if_exists='append')


def get_sites_not_in_db(engine, sites_in_catchment):
    """To only get the data for the sites which are not avialble in the database."""
    query = "select distinct site_id from hirds_rain_depth"
    gauges = engine.execute(query)
    sites = gauges.fetchall()
    sites = list(sites)
    sites_in_db = []
    for i in range(len(sites)):
        sites_in_db.append(sites[i][0])
    # yields the elements in `sites_in_catchment` that are NOT in `sites_in_db`
    sites = np.setdiff1d(sites_in_catchment, sites_in_db)
    # print(sites_in_db)
    return sites


def get_each_site_hirds_depth_data(ari, duration, site, engine, rcp=None, time_period=None):
    """Get hirds rainfall depth data from the database."""
    if rcp is None and time_period is not None:
        print("check the arguments of get_hirds_depth_data\n if rcp is None, time period should be None and vice-versa")
        sys.exit()
    elif rcp is not None and time_period is None:
        print("check the arguments of get_hirds_depth_data\n if rcp is None, time period should be None and vice-versa")
        sys.exit()
    else:
        if rcp is not None and time_period is not None:
            query = f"""select site_id, "{duration}h" from hirds_rain_depth where site_id='{site}' and ari={ari} and rcp='{rcp}' and time_period='{time_period}'"""
        else:
            query = f"""select site_id, "{duration}h" from hirds_rain_depth where site_id='{site}' and ari={ari} and rcp is null and time_period is null"""
        rain_depth = engine.execute(query)
        rain_depth = list(rain_depth.fetchone())
        return rain_depth


def check_table_exists(engine):
    """Check if the region_geometry table exists in the database."""
    insp = sqlalchemy.inspect(engine)
    table_exist = insp.has_table("hirds_rain_depth", schema="public")
    return table_exist


def add_all_sites_hirds_data_to_db(path, site_ids):
    """Get data for all the sites to the database."""
    for site_id in site_ids:
        filename = fr'{path}\{site_id}_depth.csv'
        get_data_from_hirds(site_id, filename)
        add_one_site_hirds_data_to_db(filename, site_id, engine)


def hirds_depths_to_db(engine, file, path, ari, duration, rcp=None, time_period=None):
    """Take inputs from the user, check if the data exists in the database.

    If data is not avaibale, it is downloaded first.
    """
    catchment_area = catchment_area_geometry_info(file)
    table_exits = check_table_exists(engine)
    sites_in_catchment = get_sites_in_catchment(catchment_area, engine)
    if table_exits is True:
        sites_not_in_db = get_sites_not_in_db(engine, sites_in_catchment)
        site_ids = sites_not_in_db
        if site_ids.size != 0:
            add_all_sites_hirds_data_to_db(path, site_ids)
        else:
            print("sites for the requested catchment available in the database.")
    else:
        site_ids = sites_in_catchment
        if site_ids != 0:
            add_all_sites_hirds_data_to_db(path, site_ids)
        else:
            print("There are no sites within the requested catchment area, select a wider area")


def hirds_depths_from_db(engine, file, path, ari, duration, rcp=None, time_period=None):
    """Get the list of depths and site's id of each sites and return in the dataframe format."""
    hirds_depths_to_db(engine, file, path, ari, duration)
    catchment_area = catchment_area_geometry_info(file)
    sites_in_catchment = get_sites_in_catchment(catchment_area, engine)

    depths_list = []
    for site_id in sites_in_catchment:
        rain_depth = get_each_site_hirds_depth_data(ari, duration, site_id, engine, rcp=None, time_period=None)
        depths_list.append(rain_depth)
    rain_depth_data = pd.DataFrame((depths_list), columns=['site_id', 'depth'])
    return rain_depth_data


if __name__ == "__main__":
    engine = setup_environment.get_database()
    file = r'P:\Data\catch5.shp'
    path = r"\\file\Research\FloodRiskResearch\DigitalTwin\hirds_depth_data"
    ari = 100
    duration = 24
    rcp = "2.6"
    time_period = "2031-2050"
    depths_data = hirds_depths_from_db(file, path, ari, duration)
    print(depths_data)
