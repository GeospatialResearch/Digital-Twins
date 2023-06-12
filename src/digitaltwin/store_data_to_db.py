# -*- coding: utf-8 -*-
"""
@Description:
@Author: sli229
"""

import logging

import geopandas as gpd
import pandas as pd
from sqlalchemy.engine import Engine

from src.digitaltwin import tables
from src.digitaltwin.get_data_using_geoapis import get_data_from_stats_nz, get_data_from_linz, get_data_from_mfe

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def store_regional_council_to_db(
        engine: Engine,
        layer_id: int,
        clipped: bool,
        crs: int = 2193,
        bounding_polygon: gpd.GeoDataFrame = None,
        verbose: bool = True) -> None:
    table_name = "region_geometry_clipped" if clipped else "region_geometry"
    if tables.check_table_exists(engine, table_name):
        log.info(f"Table '{table_name}' already exists in the database.")
    else:
        regional_council = get_data_from_stats_nz(layer_id, crs, bounding_polygon, verbose)
        regional_council.to_postgis(table_name, engine, index=False, if_exists="replace")
        log.info(f"Added {table_name} data (StatsNZ {layer_id}) to the database.")


def store_sea_drain_catchments_to_db(
        engine: Engine,
        layer_id: int = 99776,
        crs: int = 2193,
        bounding_polygon: gpd.GeoDataFrame = None,
        verbose: bool = True) -> None:
    table_name = "sea_draining_catchments"
    if tables.check_table_exists(engine, table_name):
        log.info(f"Table '{table_name}' already exists in the database.")
    else:
        sdc_data = get_data_from_mfe(layer_id, crs, bounding_polygon, verbose)
        sdc_data.to_postgis(table_name, engine, index=False, if_exists="replace")
        log.info(f"Added Sea-draining Catchments data (MFE {layer_id}) to the database.")


def get_road_id_not_in_db(
        engine: Engine,
        table_name: str,
        nz_roads: gpd.GeoDataFrame) -> set:
    query = f"SELECT DISTINCT road_id FROM {table_name};"
    road_id_in_db = set(pd.read_sql_query(query, engine)["road_id"])
    nz_roads_id = set(nz_roads["road_id"])
    road_id_not_in_db = nz_roads_id - road_id_in_db
    return road_id_not_in_db


def add_nz_roads_to_db(
        engine: Engine,
        table_name: str,
        layer_id: int,
        crs: int = 2193,
        bounding_polygon: gpd.GeoDataFrame = None,
        verbose: bool = True) -> None:
    nz_roads = get_data_from_linz(layer_id, crs, bounding_polygon, verbose)
    road_id_not_in_db = get_road_id_not_in_db(engine, table_name, nz_roads)

    if road_id_not_in_db:
        nz_roads_not_in_db = nz_roads[nz_roads['road_id'].isin(road_id_not_in_db)]
        nz_roads_not_in_db.to_postgis(table_name, engine, index=False, if_exists="append")
        log.info(f"Added {table_name} data (LINZ {layer_id}) for the catchment area to the database.")
    else:
        log.info(f"{table_name} data for the requested catchment area already in the database.")


def store_nz_roads_to_db(
        engine: Engine,
        layer_id: int,
        crs: int = 2193,
        bounding_polygon: gpd.GeoDataFrame = None,
        verbose: bool = True) -> None:
    table_name = "nz_roads"
    if tables.check_table_exists(engine, table_name):
        add_nz_roads_to_db(engine, table_name, layer_id, crs, bounding_polygon, verbose)
    else:
        nz_roads = get_data_from_linz(layer_id, crs, bounding_polygon, verbose)
        if not nz_roads.empty:
            nz_roads.to_postgis(table_name, engine, index=False, if_exists="replace")
            log.info(f"Added {table_name} data (LINZ {layer_id}) for the catchment area to the database.")
        else:
            log.info("The requested catchment area does not contain any roads.")
