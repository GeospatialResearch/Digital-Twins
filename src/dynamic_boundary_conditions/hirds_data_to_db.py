# -*- coding: utf-8 -*-
"""
Created on Wed Nov 24 12:51:08 2021.

@author: pkh35
"""

import geopandas as gpd
import pyproj
from shapely.ops import cascaded_union
from geovoronoi import voronoi_regions_from_coords, points_to_coords
import matplotlib.pyplot as plt
from geovoronoi.plotting import subplot_for_map, plot_voronoi_polys_with_points_in_area
import pandas as pd
from shapely.geometry import Point
import numpy as np
import sqlalchemy
from geoalchemy2 import Geometry
from shapely.ops import transform
from selenium import webdriver
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import os
import time
import shutil
import glob
import csv
from src.digitaltwin import setup_environment

file = r'P:\Data\catch.shp'
catchment = gpd.read_file(file)
catchment = catchment.to_crs(4326)
catchment_area = catchment.geometry[0]

engine = setup_environment.get_database()

# Store hirds gauging information in the database
path = r'src\HIRDS_gauge_details_V4_20180416.csv'
hirds = pd.read_csv(path)
geometry = [Point(xy) for xy in zip(hirds['Longitude'], hirds['Latitude'])]
crs = 'EPSG:4326'
hirds_gauge = gpd.GeoDataFrame(hirds, crs=crs, geometry=geometry)
if sqlalchemy.inspect(engine).has_table("hirds_gauges") is False:
    hirds_gauge.to_postgis('hirds_gauges', engine, if_exists='replace',
                           index=False, dtype={'geometry': Geometry(geometry_type='POINT', srid=4326)})
else:
    print("Hirds gauges information exists in the database.To add the recent copy of the hirds gauges in the database\
          Go to: 'https://niwa.co.nz/information-services/hirds/help' and store the csv file in the src directory")

# Get gauges within the catchment area.
query = f'''select * from public.hirds_gauges f
    where ST_Intersects(f.geometry, ST_GeomFromText('{catchment_area}', 4326))'''
gauges_in_catchment = pd.read_sql_query(query, engine)
gauges_in_catchment['geometry'] = gpd.GeoSeries.from_wkb(gauges_in_catchment['geometry'])
gauges_in_catchment = gpd.GeoDataFrame(gauges_in_catchment, geometry='geometry')
gauges = gauges_in_catchment.geometry
gauges_in_catchment['exists'] = gauges.within(catchment_area)
gauges_in_polygon = gauges_in_catchment.loc[gauges_in_catchment['exists'] == True]
gauges_in_polygon['order'] = np.arange(len(gauges_in_polygon))

"""In mathematics, a Voronoi diagram is a partition of a plane into regions close to each of a given set of objects"""

boundary_shape = cascaded_union(catchment.geometry)
coords = points_to_coords(gauges_in_polygon.geometry)
region_polys, region_pts = voronoi_regions_from_coords(coords, catchment_area, per_geom=False)

# fig, ax = subplot_for_map()
# plot_voronoi_polys_with_points_in_area(ax, catchment_area, region_polys, coords, region_pts)
# plt.show()

sites_list = []
sites_in_catchment = pd.DataFrame()
for key, value in region_pts.items():
    site = gauges_in_polygon.loc[(gauges_in_polygon['order'] == value[0])]
    sites_list.append(site)
sites_in_catchment = pd.concat(sites_list)

wgs84 = pyproj.CRS('EPSG:4326')
utm = pyproj.CRS('EPSG:3857')
project = pyproj.Transformer.from_crs(wgs84, utm, always_xy=True).transform
for i,ind in zip(range(len(region_polys)), sites_in_catchment.index):
    projected_area = transform(project, region_polys[i]).area
    # Print the area in km^2
    print(i, sites_in_catchment['Site ID'][ind], projected_area*0.001)

directory = "ddf_data"
parent_dir = r"\\file\Usersp$\pkh35\Home\Downloads"

path = os.path.join(parent_dir, directory)
# Check whether the specified path exists or not
isExist = os.path.exists(path)
if not isExist:
    os.mkdir(path)
else:
    print("data will be saved in", path)


def get_data_from_csv(filename, site, n):
    """Read data of the diffrent time period and return a dataframe."""
    hirds_data = pd.read_csv(filename, skiprows=n, nrows=12, index_col=None, quotechar='"')
    hirds_data['site_id'] = site
    # print(hirds_data)
    hirds_data.columns = hirds_data.columns.str.lower()
    return hirds_data


def get_hirds_data_from_site(site_id, path, engine):
    """Get the site ids and browse automatically from hirds website."""
    options = webdriver.ChromeOptions()
    prefs = {'download.default_directory': f'{path}'}
    options.add_experimental_option('prefs', prefs)
    driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)
    driver.get('https://hirds.niwa.co.nz/')
    id_box = driver.find_element(By.NAME, 'siteId')
    # for site_id in sites_in_catchment['Site ID']:
    id_box.clear()
    # Send id information
    id_box.send_keys(site_id)
    driver.find_element(By.CSS_SELECTOR, "input[type='radio'][value='depth']").click()
    time.sleep(2)
    driver.find_element(By.XPATH, "/html/body/hirds-app/main/div/hirds-home/div[1]/div[2]/div/div[2]/hirds-site-search/div/div/form/div[2]/button").click()
    time.sleep(5)
    driver.find_element(By.XPATH, "/html/body/hirds-app/main/div/hirds-home/div[2]/div/div/div[1]/span[1]").click()
    print(f"downloading file for site: {site_id}")
    time.sleep(3)
    filename = max([path + "\\" + f for f in os.listdir(path)], key=os.path.getctime)
    site_ids = []
    with open(filename) as file_name:
        reader = csv.reader(file_name)
        for i, row in enumerate(reader):
            if i == 2:
                site_ids.append(row[0][9:].strip())
    site = site_ids[0]
    historical_data = get_data_from_csv(filename, site, n=12)
    historical_data.to_sql('hirds_rain_depth_historical', engine, index=False, if_exists='append')
    rcp2_data_2031 = get_data_from_csv(filename, site, n=40)
    rcp2_data_2031.to_sql('hirds_rain_depth_rcp2.6_2031_2050', engine, index=False, if_exists='append')
    rcp2_data_2081 = get_data_from_csv(filename, site, n=54)
    rcp2_data_2081.to_sql('hirds_rain_depth_rcp2.6_2081_2100', engine, index=False, if_exists='append')

    rcp4_data_2031 = get_data_from_csv(filename, site, n=68)
    rcp4_data_2031.to_sql('hirds_rain_depth_rcp4.5_2031_2050', engine, index=False, if_exists='append')
    rcp4_data_2081 = get_data_from_csv(filename, site, n=82)
    rcp4_data_2081.to_sql('hirds_rain_depth_rcp4.5_2081_2100', engine, index=False, if_exists='append')

    rcp6_data_2031 = get_data_from_csv(filename, site, n=96)
    rcp6_data_2031.to_sql('hirds_rain_depth_rcp6_2031_2050', engine, index=False, if_exists='append')
    rcp6_data_2081 = get_data_from_csv(filename, site, n=110)
    rcp6_data_2081.to_sql('hirds_rain_depth_rcp6_2081_2100', engine, index=False, if_exists='append')

    rcp8_data_2031 = get_data_from_csv(filename, site, n=124)
    rcp8_data_2031.to_sql('hirds_rain_depth_rcp8.5_2031_2050', engine, index=False, if_exists='append')
    rcp8_data_2081 = get_data_from_csv(filename, site, n=138)
    rcp8_data_2081.to_sql('hirds_rain_depth_rcp8.5_2081_2100', engine, index=False, if_exists='append')

    shutil.move(filename, os.path.join(path, fr"depth_{site}.csv"))
    print(f"file downloaded for site: {site}")


def get_stored_sites_info(path):
    """Read the site_ids from the csv files stored in the local directory."""
    site_ids = []
    for file_name in glob.glob(os.path.join(path, "*.csv")):
        with open(file_name) as file_name:
            reader = csv.reader(file_name)
            for i, row in enumerate(reader):
                if i == 2:
                    site_ids.append(row[0][9:].strip())
    return site_ids


for site_id in sites_in_catchment['Site ID']:
    site_ids = get_stored_sites_info(path)
    if site_id in site_ids:
        print(f"file for site {site_id} exist in the database")
    else:
        get_hirds_data_from_site(site_id, path, engine)
        print(f"{site_id} is not present")


def get_hirds_data_from_db(sites_in_catchment, engine):
    """Get depth information of the sites within the catchment."""
    for site_id in sites_in_catchment['Site ID']:
        print(site_id)
        query = f"select * from hirds_rain_depth_historical where site_id = '{site_id}'"
        # data = engine.execute(query)
        data = pd.read_sql_query(query, engine)
        print(data)


get_hirds_data_from_db(sites_in_catchment, engine)
