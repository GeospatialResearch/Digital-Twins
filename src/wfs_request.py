# -*- coding: utf-8 -*-
"""
Created on Fri Aug 13 09:37:50 2021

@author: pkh35
"""
from urllib.parse import urlparse
import urllib
import requests
import geopandas
import pandas as pd
import pyproj
path = 'C:\\Users\\pkh35\\Anaconda3\\envs\\digitaltwin\\Library\\share\\proj'
pyproj.datadir.set_data_dir(path)
pyproj.datadir.get_data_dir()


def data_from_apis(engine, key, base_url, params, geometry_type, source_name, geom):
    """Construct the api query for the requested area
    and save it as a cache table"""

    params['cql_filter'] = f"bbox({geometry_type}, {geom.bounds[0]},\
        {geom.bounds[1]}, {geom.bounds[2]}, {geom.bounds[3]})"
    parsed_api = urlparse(base_url)
    base_url = urllib.parse.urlunparse((parsed_api.scheme, parsed_api.netloc,
                                        parsed_api.path.replace
                                        ("API_KEY", key), "",  "", ""))
    """
    According to PsotgreSQL naming convention,
    a table name must start with a letter or an underscore;
    the rest of the string can contain letters, digits, and underscores.
    In our database,names of the tables are based on souce_name column which
    in some cases starts with integer, e.g. "101292-nz-building-outlines",
    so "_" is appended before adding table to the database
    """
    table_name = "_"+''.join(char for char in source_name if char.isalnum())

    try:
        response = requests.get(base_url, params=params)

    except Exception as error:
        print(error)
        print("Exception TYPE:", type(error))

    response_data = geopandas.read_file(response.text)
    response_data['geometry'] = response_data.geometry.set_crs(
        "EPSG:2193", allow_override=True)

    response_data.to_postgis(table_name, engine, index=False, if_exists='append')
    engine.execute("update %(table_name)s set geometry =\
                   st_flipcoordinates(geometry)", ({'table_name': table_name}))

    # delete duplicate rows from the newly created tables if exists
    engine.execute("DELETE FROM %(table_name)s a USING (\
      SELECT MIN(ctid) as ctid, id\
        FROM %(table_name)s \
        GROUP BY id HAVING COUNT(*) > 1\
      ) b WHERE a.id = b.id \
      AND a.ctid <> b.ctid" % ({'table_name': table_name}))


def access_api_info(engine, source_name):
    queries = engine.execute("select source_apis,query_dictionary,\
                             geometry_col_name,source_name from apilinks\
                             where source_name IN %(source_name)s",
                             ({'source_name': source_name}))
    api_record = []
    for query in queries:
        api_record.append(query)
    api_records = pd.DataFrame(api_record, columns=['source_apis',
                                                    'query_dictionary',
                                                    'geometry_col_name',
                                                    'source_name'])
    return api_records
