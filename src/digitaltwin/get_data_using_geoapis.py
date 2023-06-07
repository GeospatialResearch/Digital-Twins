# -*- coding: utf-8 -*-
"""
@Description:
@Author: sli229
"""

import logging

import geopandas as gpd
import geoapis.vector
from sqlalchemy.engine import Engine

from src import config
from src.digitaltwin import tables

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def get_data_from_stats_nz(
        layer_id: int,
        crs: int = 2193,
        bounding_polygon: gpd.GeoDataFrame = None,
        verbose: bool = True) -> gpd.GeoDataFrame:
    stats_nz_api_key = config.get_env_variable("StatsNZ_API_KEY")
    vector_fetcher = geoapis.vector.StatsNz(
        key=stats_nz_api_key,
        bounding_polygon=bounding_polygon,
        verbose=verbose,
        crs=crs)
    stats_data = vector_fetcher.run(layer_id)
    return stats_data


def get_regional_council(
        layer_id: int,
        crs: int = 2193,
        bounding_polygon: gpd.GeoDataFrame = None,
        verbose: bool = True) -> gpd.GeoDataFrame:
    regional_council = get_data_from_stats_nz(layer_id, crs, bounding_polygon, verbose)
    regional_council.columns = regional_council.columns.str.lower()
    regional_council['geometry'] = regional_council.pop('geometry')
    return regional_council


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
        regional_council = get_regional_council(layer_id, crs, bounding_polygon, verbose)
        regional_council.to_postgis(f"{table_name}", engine, index=False, if_exists="replace")
        log.info(f"Added {table_name} (StatsNZ {layer_id}) data to database.")


def get_data_from_mfe(
        layer_id: int,
        crs: int = 2193,
        bounding_polygon: gpd.GeoDataFrame = None,
        verbose: bool = True) -> gpd.GeoDataFrame:
    mfe_api_key = config.get_env_variable("MFE_API_KEY")
    vector_fetcher = geoapis.vector.WfsQuery(
        key=mfe_api_key,
        crs=crs,
        bounding_polygon=bounding_polygon,
        netloc_url="data.mfe.govt.nz",
        geometry_names=['GEOMETRY', 'shape'],
        verbose=verbose)
    vector_layer_data = vector_fetcher.run(layer_id)
    return vector_layer_data


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
        sdc_data.columns = sdc_data.columns.str.lower()
        sdc_data = sdc_data[['catch_id', 'shape_leng', 'shape_area', 'geometry']]
        sdc_data.to_postgis("sea_draining_catchments", engine, index=False, if_exists="replace")
        log.info("Added Sea-draining Catchments data to database.")
