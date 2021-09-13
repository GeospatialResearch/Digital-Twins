# -*- coding: utf-8 -*-
"""
Created on Mon Sep 13 15:21:34 2021

@author: pkh35
"""
import insert_api_to_table

#inputs to store in a row of apilinks table
DATA_PROVIDER = "LINZ"    
SOURCE = "101292-nz-building-outlines"
API = 'https://data.linz.govt.nz/services;key=API_KEY/wfs?service=WFS&version=2.0.0&request=GetFeature&\
    typeNames=layer-101292&outputFormat=json&SRSName=EPSG:2193&cql_filter=bbox(shape,5169354.082, 1559525.958, 5167380.381, 1558247.433 )'
URL = "https://data.linz.govt.nz/layer/101292-nz-building-outlines-all-sources/"
REGION = "New Zealand"
GEOMETRY_COLUMN = "shape"
Stats_NZ_KEY = 'your_key'

insert_api_to_table.insert_records(DATA_PROVIDER,SOURCE,API, URL, REGION,GEOMETRY_COLUMN ,Stats_NZ_KEY)