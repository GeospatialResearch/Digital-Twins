# -*- coding: utf-8 -*-
"""
Created on Thu Sep 23 08:13:42 2021.

@author: pkh35
"""
import shapely.wkt
import json
import pandas as pd
import geopandas as gpd
from geopandas import GeoSeries
import setup_environment
import tables
import wfs_request


def check_table_exist(engine, source_list):
    """To check if tables already exists in the db for the requetsed sources."""
    table = engine.execute("select table_name from information_schema.tables")
    tables_name = []
    for i in table:
        tables_name.append(i[0])

    tables_not_in_db = []
    tables_in_db = []
    for source in source_list:
        if source not in tables_name:
            tables_not_in_db.append(source)
        else:
            tables_in_db.append(source)
    return tables_in_db, tables_not_in_db


def wfs_request_from_db(engine, tables, polygon):
    """Make wfs request for the requested sources."""
    db_tbl = wfs_request.access_api_info(engine, tuple(tables))
    for i in range(len(db_tbl)):
        data_provider = db_tbl.loc[i, 'data_provider']
        base_url = db_tbl.loc[i, 'source_apis']
        layer = db_tbl.loc[i, 'layer']
        geometry_name = db_tbl.loc[i, 'geometry_col_name']
        keys = engine.execute("select key from api_keys where data_provider = %(data_provider)s", ({
                              'data_provider': data_provider}))
        key = ""
        for k in keys:
            key = key + k[0]
        table_name = db_tbl.loc[i, 'source_name']
        wfs_request.data_from_apis(engine, key, base_url, layer,
                                   geometry_name, table_name, polygon)


def get_geometry_info(engine):
    """Get the geometry of the tables that exist in the database."""
    stored_list = engine.execute("select source_list, ST_AsText(geometry) from\
                                      user_log_information")
    stored_srces = stored_list.fetchall()

    for i in range(len(stored_srces)):
        geom = stored_srces[i][1]
        srcList = stored_srces[i][0]
        srcList = json.loads(srcList)
        # added geometry column to the sorce_list dictionary
        srcList['geometry'] = geom
        return srcList


def get_data_from_apis(geometry_df, source_list):
    # connect to the database where apis are stored
    engine = setup_environment.get_database()
    geometry_df.set_crs(crs='epsg:2193', inplace=True)
    user_geometry = geometry_df.iloc[0, 0]

    tables_in_db, tables_not_in_db = check_table_exist(engine, source_list)
    source_list = tuple(source_list)

    if tables_in_db is not []:
        srcList = get_geometry_info(engine)
        for table in tables_in_db:
            if table in srcList['source_name']:
                srcList['geometry'] = shapely.wkt.loads(
                    str(srcList['geometry']))
                not_in_db_polygon = user_geometry.difference(
                    srcList['geometry'])
                if not_in_db_polygon.is_empty:
                    pass
                else:
                    polygon = gpd.GeoDataFrame(
                        GeoSeries(not_in_db_polygon))
                    polygon = polygon.rename(
                        columns={0: 'geometry'}).set_geometry('geometry')
                    polygon.set_crs(crs='epsg:2193', inplace=True)
                    wfs_request_from_db(engine, tables_in_db, polygon)

    if tables_not_in_db != []:
        wfs_request_from_db(engine, tables_not_in_db, geometry_df)

    else:
        print("data avilable in the database")

    User_log_info = tables.User_log_info
    dbsession = tables.dbsession()
    dbsession.sessionCreate(User_log_info, engine)
    user_source_list = wfs_request.get_source_from_db(engine, source_list)
    query = User_log_info(source_list=json.dumps(user_source_list,
                                                 sort_keys=True, default=str),
                          geometry=str(user_geometry))
    dbsession.runQuery(engine, query)


def get_data_from_db(geometry, source_list):
    # connect to the database where apis are stored
    engine = setup_environment.get_database()
    """Query data from the database for the requested polygon."""
    user_geometry = geometry.iloc[0, 0]
    get_data_from_apis.get_data_from_apis(engine, geometry, source_list)
    poly = "'{}'".format(user_geometry)
    for source in source_list:
        query = 'select * from "%(source)s" where ST_Intersects(geometry, ST_GeomFromText({}, 2193))' % (
            {'source': source})
        output_data = pd.read_sql_query(query.format(poly), engine)
        print(output_data)
