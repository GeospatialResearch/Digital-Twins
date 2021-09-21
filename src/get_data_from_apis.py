# -*- coding: utf-8 -*-
"""
Created on Thu Sep 16 14:44:11 2021

@author: pkh35
"""

# -*- coding: utf-8 -*-
"""
Created on Fri Aug  6 13:26:02 2021

@author: pkh35
"""


import pyproj
path = 'C:\\Users\\pkh35\\Anaconda3\\envs\\digitaltwin\\Library\\share\\proj'
pyproj.datadir.set_data_dir(path)
pyproj.datadir.get_data_dir()
import wfs_request
import pathlib
import json
import geopandas as gpd
import setup_environment
import srclist_check
import polygon_Intersection as pi
import tables

# connect to the database where apis are stored
engine1 = setup_environment()

# load in the instructions, get the source list and polygon from the user
FILE_PATH = pathlib.Path().cwd() / pathlib.Path("test6.json")
with open(FILE_PATH, 'r') as file_pointer:
    instructions = json.load(file_pointer)

source_list = tuple(instructions['source_name'])
user_input_df = gpd.GeoDataFrame.from_features(instructions["features"])
geometry = user_input_df.iloc[0, 0]


User_log_info = tables.User_log_info
dbsession = tables.dbsession()
dbsession.sessionCreate(User_log_info, engine1)

not_available_src_list, user_source_list = srclist_check.\
    srcListCheck(engine1, source_list, str(geometry))

poly_not_available = pi.get_intersection(engine1, str(geometry))

query = User_log_info(source_list=json.dumps(user_source_list, sort_keys=True,default=str), geometry=str(geometry))
dbsession.runQuery(engine1, query)

"""take the user entered source list and polygon not available,
get apis and stored data in the tables
get the src not available for intersecting part and get the available polygon,
get apis and stored data in the tables"""

if poly_not_available is not None:
    # chnage it to not available sourcelist later
    df = wfs_request.access_api_info(engine1, source_list)
    key = 'e33292c76462449eb31a8c8c011c16eb'
    for i in range(len(df)):
        wfs_request.data_from_apis(engine1, key, df.loc[i, 'source_apis'],
                                   df.loc[i, 'query_dictionary'],
                                   df.loc[i, 'geometry_col_name'],
                                   df.loc[i, 'source_name'], poly_not_available)
else:
    # get tables from the database for the AOI
    pass
