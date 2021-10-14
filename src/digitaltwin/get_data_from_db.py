# -*- coding: utf-8 -*-
"""
Created on Mon Sep 20 09:18:56 2021.

@author: pkh35
"""
import pandas as pd
import geopandas as gpd
import pathlib
import json
import get_data_from_apis
import setup_environment


def get_data_from_db(engine, geometry, source_list):
    """Query data from the database for the requested polygon."""
    get_data_from_apis.get_data_from_apis(engine, geometry, source_list)
    poly = "'{}'".format(geometry)
    for source in source_list:
        query = 'select * from "%(source)s" where ST_Intersects(geometry, ST_GeomFromText({}, 2193))' % (
            {'source': source})
        output_data = pd.read_sql_query(query.format(poly), engine)
        print(source, output_data)


if __name__ == "__main__":
    # load in the instructions, get the source list and polygon from the user
    FILE_PATH = pathlib.Path().cwd() / pathlib.Path("test1.json")
    with open(FILE_PATH, 'r') as file_pointer:
        instructions = json.load(file_pointer)
    source_list = tuple(instructions['source_name'])
    geometry = gpd.GeoDataFrame.from_features(instructions["features"])
    # connect to the database where apis are stored
    engine = setup_environment.get_database()
    get_data_from_db(engine, geometry, source_list)
