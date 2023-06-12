# -*- coding: utf-8 -*-
"""
@Description:
@Author: sli229
"""

import logging

import geopandas as gpd
from sqlalchemy.engine import Engine

from src.digitaltwin import tables
from src.digitaltwin.get_data_using_geoapis import get_data_from_stats_nz, get_data_from_mfe

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
        regional_council.to_postgis(f"{table_name}", engine, index=False, if_exists="replace")
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
        sdc_data.to_postgis("sea_draining_catchments", engine, index=False, if_exists="replace")
        log.info(f"Added Sea-draining Catchments data (MFE {layer_id}) to the database.")
