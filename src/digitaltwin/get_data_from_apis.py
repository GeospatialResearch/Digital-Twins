# -*- coding: utf-8 -*-
"""
Created on Thu Sep 23 08:13:42 2021.

@author: pkh35, sli229
"""
import json
import logging

import geopandas as gpd
import shapely.wkt

from src import config
from src.digitaltwin import tables
from src.digitaltwin import wfs_request

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def check_table_exist(engine, source_list):
    """To check if tables already exists in the database for the requested
    sources."""
    table = engine.execute(
        "SELECT table_name FROM information_schema.tables\
                           WHERE table_schema='public' AND table_type='BASE TABLE'"
    )
    table_names = []
    for i in table:
        table_names.append(i[0])
    tables_not_in_db = []
    tables_in_db = []
    for source in source_list:
        if source not in table_names:
            tables_not_in_db.append(source)
        else:
            tables_in_db.append(source)
    return tables_in_db, tables_not_in_db


def wfs_request_from_db(engine, table_names, polygon):
    """Make wfs request for the requested sources.
    table_names is source_name ('_50329-nz-road-centrelines',
                           '_50319-nz-railway-centrelines')
    """
    db_tbl = wfs_request.access_api_info(engine, tuple(table_names))
    for i in range(len(db_tbl)):
        data_provider = db_tbl.loc[i, "data_provider"]
        layer = db_tbl.loc[i, "layer"]
        base_url = db_tbl.loc[i, "source_api"]
        geometry_name = db_tbl.loc[i, "geometry_col_name"]
        table_name = db_tbl.loc[i, "source_name"]
        key_name = f"{data_provider}_API_KEY"
        key = config.get_env_variable(key_name)
        wfs_request.data_from_apis(
            engine, key, base_url, layer, geometry_name, table_name, polygon
        )


def get_geometry_info(engine):
    """Get the geometry of the tables that exist in the database."""
    stored_list = engine.execute(
        "SELECT DISTINCT source_list, ST_AsText(geometry) FROM user_log_information"
    )
    stored_srces = stored_list.fetchall()

    for i in range(len(stored_srces)):
        src_list = stored_srces[i][0]
        geom = stored_srces[i][1]
        src_list = json.loads(src_list)
        # added geometry column to the source_list dictionary
        src_list["geometry"] = geom
        return src_list


def get_data_from_apis(engine, geometry_df, source_list):
    """
    Check if the requested polygon intersects with the existing polygon.
    Get non-intersecting part of the requested polygon and make wfs request.
    If table not in the database, simply make wfs request.
    """
    geometry_df.set_crs(crs="epsg:2193", inplace=True)
    user_geometry = geometry_df.iloc[0, 0]

    tables_in_db, tables_not_in_db = check_table_exist(engine, source_list)
    source_list = tuple(source_list)

    if tables_in_db != []:
        src_list = get_geometry_info(engine)
        for table in tables_in_db:
            if table in src_list["source_name"]:
                src_list["geometry"] = shapely.wkt.loads(str(src_list["geometry"]))
                not_in_db_polygon = user_geometry.difference(src_list["geometry"])
                if not_in_db_polygon.is_empty:
                    log.info("catchment data already available in the database")
                else:
                    polygon = gpd.GeoDataFrame(gpd.GeoSeries(not_in_db_polygon))
                    polygon = polygon.rename(columns={0: "geometry"})
                    polygon.set_geometry("geometry", crs="epsg:2193", inplace=True)
                    wfs_request_from_db(engine, tables_in_db, polygon)
    if len(tables_not_in_db) > 0:
        wfs_request_from_db(engine, tables_not_in_db, geometry_df)
    else:
        log.info("data available in the database")
    # store user information in the table
    user_source_list = wfs_request.get_source_from_db(engine, source_list)
    user_log_info = tables.User_log_info
    dbsession = tables.dbsession()
    dbsession.sessionCreate(user_log_info, engine)
    query = user_log_info(
        source_list=json.dumps(user_source_list, sort_keys=True, default=str),
        geometry=str(user_geometry),
    )
    dbsession.runQuery(engine, query)
