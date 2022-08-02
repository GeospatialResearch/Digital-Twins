# -*- coding: utf-8 -*-
"""
Created on Mon Sep 20 09:18:56 2021.

@author: pkh35, sli229
"""

import geopandas as gpd
import pathlib
import json
import pandas as pd
from ...util import setup_environment
from . import get_data_from_apis


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
