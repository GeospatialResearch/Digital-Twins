# -*- coding: utf-8 -*-
"""
Created on Mon Sep 20 09:18:56 2021.

@author: pkh35, sli229
"""

import json
import pathlib
from typing import List, Optional

import geopandas as gpd
import pandas as pd

from . import get_data_from_apis
from ...util import setup_environment


def fetch_updated_vector_data(data_sources: Optional[List[str]] = None) -> List[gpd.GeoDataFrame]:
    """Checks if requested_data needs to be updated, updates it in the database if needed, then returns data.
    :param data_sources List of source names of data required. If this is None then all vector data is fetched"""
    if data_sources is None:
        data_sources = get_all_vector_source_names()
    if data_needs_update(data_sources):
        update_data(data_sources)
    return get_data_from_db(data_sources)


def get_all_vector_source_names() -> List[str]:
    """Returns a list of all source names for data sources stored in the database"""
    # TODO: Implement
    pass


def get_data_from_db(data_sources: List[str]) -> List[gpd.GeoDataFrame]:
    """Retrieves the vector data of each data source in data_sources"""
    # TODO: Implement
    pass


def get_data_from_external_services(data_sources: List[str]) -> List[gpd.GeoDataFrame]:
    """Retrieves each data source from external APIs"""
    # TODO: Implement
    pass


def update_data(data_sources: List[str]):
    """Updates database from external sources for each source_name in data_sources"""
    # TODO: Implement
    pass


def data_needs_update(requested_data: List[str]) -> bool:
    """Returns true if requested_data is non-existent or needs to be updated"""
    # TODO: Add issue to implement update check
    return False


def get_data_from_db(engine, geometry: gpd.GeoDataFrame, source_list: tuple):
    """Perform spatial query within the database for the requested polygon."""
    get_data_from_apis.get_data_from_apis(engine, geometry, source_list)
    user_geometry = geometry.iloc[0, 0]
    poly = "'{}'".format(user_geometry)
    for source in source_list:
        #  2193 is the code for the NZTM projection
        query = f'select * from "{source}" where ST_Intersects(geometry, ST_GeomFromText({poly}, 2193))'
        output_data = pd.read_sql_query(query, engine)
        output_data["geometry"] = gpd.GeoSeries.from_wkb(output_data["geometry"])
        output_data = gpd.GeoDataFrame(output_data, geometry="geometry")
        print(source)
        print(output_data)


def main():
    engine = setup_environment.get_database()
    # load in the instructions, get the source list and polygon from the user
    FILE_PATH = pathlib.Path().cwd() / pathlib.Path(
        "src/instructions_get_data_from_db.json"
    )
    with open(FILE_PATH, "r") as file_pointer:
        instructions = json.load(file_pointer)
    source_list = tuple(instructions["source_name"])
    geometry = gpd.GeoDataFrame.from_features(instructions["features"], crs=2193)
    get_data_from_db(engine, geometry, source_list)


if __name__ == "__main__":
    main()
