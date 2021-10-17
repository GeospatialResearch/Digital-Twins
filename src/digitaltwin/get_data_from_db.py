# -*- coding: utf-8 -*-
"""
Created on Mon Sep 20 09:18:56 2021.

@author: pkh35
"""

import geopandas as gpd
import pathlib
import json
import get_data_from_apis


if __name__ == "__main__":
    # load in the instructions, get the source list and polygon from the user
    FILE_PATH = pathlib.Path().cwd() / pathlib.Path("../test1.json")
    with open(FILE_PATH, 'r') as file_pointer:
        instructions = json.load(file_pointer)
    source_list = tuple(instructions['source_name'])
    geometry = gpd.GeoDataFrame.from_features(instructions["features"])
    get_data_from_apis.get_data_from_db(geometry, source_list)
