# -*- coding: utf-8 -*-
"""
Created on Thu Sep 16 14:44:11 2021

@author: pkh35
"""

import json
import pathlib

import geopandas as gpd
from geopandas import GeoSeries

import polygon_Intersection as pi
import setup_environment
import sources_from_db
import tables
import wfs_request

# connect to the database where apis are stored
engine1 = setup_environment.get_database()

# load in the instructions, get the source list and polygon from the user
FILE_PATH = pathlib.Path().cwd() / pathlib.Path("test6.json")
with open(FILE_PATH, 'r') as file_pointer:
    instructions = json.load(file_pointer)

source_list = tuple(instructions['source_name'])

user_input_df = gpd.GeoDataFrame.from_features(instructions["features"])
user_input_df.set_crs(crs='epsg:2193', inplace=True)
geometry = user_input_df.iloc[0, 0]

user_source_list = sources_from_db.get_source_from_db(engine1, source_list)

User_log_info = tables.User_log_info
dbsession = tables.dbsession()
dbsession.sessionCreate(User_log_info, engine1)

poly_not_available = pi.get_intersection(engine1, str(geometry))

polygon = gpd.GeoDataFrame(GeoSeries(poly_not_available))
polygon = polygon.rename(columns={0: 'geometry'}).set_geometry('geometry')
polygon.set_crs(crs='epsg:2193', inplace=True)

query = User_log_info(source_list=json.dumps(
    user_source_list, sort_keys=True, default=str), geometry=str(geometry))
dbsession.runQuery(engine1, query)

"""take the user entered source list and polygon not available,
get apis and stored data in the tables"""

if poly_not_available is not None:
    df = wfs_request.access_api_info(engine1, source_list)
    for i in range(len(df)):
        data_provider = df.loc[i, 'data_provider']
        base_url = df.loc[i, 'source_apis']
        layer = df.loc[i, 'layer']
        geometry_name = df.loc[i, 'geometry_col_name']
        keys = engine1.execute("select key from api_keys where data_provider\
                               = %(data_provider)s", ({'data_provider': data_provider}))
        key = ""
        for k in keys:
            key = key + k[0]
        table_name = df.loc[i, 'source_name']
        wfs_request.data_from_apis(engine1, key, base_url, layer,
                                   geometry_name, table_name, polygon)
else:
    # adding spatial query function later
    print("data avilable in the database")
