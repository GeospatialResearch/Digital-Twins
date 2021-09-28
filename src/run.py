# -*- coding: utf-8 -*-
"""
Created on Mon Sep 13 15:21:34 2021

@author: pkh35
"""
import json
import pathlib
import insert_api_to_table

# load in the instructions to add building outlines api from LINZ
file_path = pathlib.Path().cwd() / pathlib.Path("instructions_statsnz.json")
with open(file_path, 'r') as file_pointer:
    instructions = json.load(file_pointer)

SOURCE = instructions['instructions']['source_name']
REGION = instructions['instructions']['region_name']
GEOMETRY_COLUMN = instructions['instructions']['geometry_col_name']
URL = instructions['instructions']['url']
API = instructions['instructions']['api']
DATA_PROVIDER = instructions['instructions']['data_provider']
LAYER = instructions['instructions']['layer']
"""get stats NZ key from:
https://datafinder.stats.govt.nz/layer/105133-regional-council-2021-generalised/webservices/"""
Stats_NZ_KEY = 'YOUR_KEY'

# call the function to insert record in apilinks table
insert_api_to_table.insert_records(DATA_PROVIDER, SOURCE, API, REGION,
                                   GEOMETRY_COLUMN, URL, LAYER, Stats_NZ_KEY)
