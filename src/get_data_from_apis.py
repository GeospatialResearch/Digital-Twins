# -*- coding: utf-8 -*-
"""
Created on Thu Sep 23 08:13:42 2021

@author: pkh35
"""
import shapely.wkt
import pathlib
import json
import geopandas as gpd
from geopandas import GeoSeries
import setup_environment
import tables
import wfs_request

# connect to the database where apis are stored
engine = setup_environment.get_database()

# load in the instructions, get the source list and polygon from the user
FILE_PATH = pathlib.Path().cwd() / pathlib.Path("test1.json")
with open(FILE_PATH, 'r') as file_pointer:
    instructions = json.load(file_pointer)

source_list = tuple(instructions['source_name'])
geometry_df = gpd.GeoDataFrame.from_features(instructions["features"])
geometry_df.set_crs(crs='epsg:2193', inplace=True)
user_geometry = geometry_df.iloc[0, 0]

table = engine.execute("select table_name from information_schema.tables")
tables_name = []
for i in table:
    tables_name.append(i[0])

tables_not_in_db = []
tables_in_db = []
for source in instructions['source_name']:
    if source not in tables_name:
        tables_not_in_db.append(source)
    else:
        tables_in_db.append(source)

if tables_in_db != []:
    stored_list = engine.execute("select source_list, ST_AsText(geometry) from\
                                  user_log_information")
    stored_srces = stored_list.fetchall()
    for i in range(len(stored_srces)):
        geom = stored_srces[i][1]
        srcList = stored_srces[i][0]
        srcList = json.loads(srcList)
        geom = {'geometry': stored_srces[i][1]}
        # added geometry column to the sorce_list dictionary
        srcList.update(geom)

        for table in tables_in_db:
            if table in srcList['source_name']:
                srcList['geometry'] = shapely.wkt.loads(
                    str(srcList['geometry']))
                not_in_db_polygon = user_geometry.difference(
                    srcList['geometry'])
                if not_in_db_polygon.is_empty:
                    # adding spatial query function later
                    print("data available in the database")
                else:
                    polygon = gpd.GeoDataFrame(GeoSeries(not_in_db_polygon))
                    polygon = polygon.rename(
                        columns={0: 'geometry'}).set_geometry('geometry')
                    polygon.set_crs(crs='epsg:2193', inplace=True)
                    db_tbl = wfs_request.access_api_info(
                        engine, tuple(tables_in_db))
                    for i in range(len(db_tbl)):
                        data_provider = db_tbl.loc[i, 'data_provider']
                        base_url = db_tbl.loc[i, 'source_apis']
                        layer = db_tbl.loc[i, 'layer']
                        geometry_name = db_tbl.loc[i, 'geometry_col_name']
                        keys = engine.execute("select key from api_keys where data_provider\
                                    = %(data_provider)s", ({'data_provider': data_provider}))
                        key = ""
                        for k in keys:
                            key = key + k[0]
                        table_name = db_tbl.loc[i, 'source_name']
                        wfs_request.data_from_apis(engine, key, base_url, layer,
                                                   geometry_name, table_name, polygon)


if tables_not_in_db != []:
    db_tbl = wfs_request.access_api_info(engine, tuple(tables_not_in_db))
    for i in range(len(db_tbl)):
        data_provider = db_tbl.loc[i, 'data_provider']
        base_url = db_tbl.loc[i, 'source_apis']
        layer = db_tbl.loc[i, 'layer']
        geometry_name = db_tbl.loc[i, 'geometry_col_name']
        keys = engine.execute("select key from api_keys where data_provider\
                                = %(data_provider)s", ({'data_provider': data_provider}))
        key = ""
        for k in keys:
            key = key + k[0]
        table_name = db_tbl.loc[i, 'source_name']
        wfs_request.data_from_apis(engine, key, base_url, layer,
                                   geometry_name, table_name, geometry_df)

else:
    # adding spatial query function later
    print("data avilable in the database")

User_log_info = tables.User_log_info
dbsession = tables.dbsession()
dbsession.sessionCreate(User_log_info, engine)
user_source_list = wfs_request.get_source_from_db(engine, source_list)
query = User_log_info(source_list=json.dumps(user_source_list,
                                             sort_keys=True, default=str),
                      geometry=str(user_geometry))
dbsession.runQuery(engine, query)
