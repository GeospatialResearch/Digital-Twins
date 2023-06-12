# -*- coding: utf-8 -*-
"""
@Description:
@Author: sli229
"""

import geopandas as gpd
import geoapis.vector

from src import config


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
    vector_data = vector_fetcher.run(layer_id)
    return vector_data


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
    vector_data = vector_fetcher.run(layer_id)
    return vector_data
