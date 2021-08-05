# -*- coding: utf-8 -*-
"""
Created on Fri Aug  6 09:23:01 2021

@author: pkh35
"""


import setup_environment
from api_values import records

engine = setup_environment.get_database()
records = records()
try:
    create_table = "CREATE TABLE IF NOT EXISTS public.apilinks(unique_id uuid NOT NULL DEFAULT uuid_generate_v4(),\
        source_name character varying(255),source_apis character varying(65535),\
        access_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,url character varying(67777),\
        api_modified_date date,region_name character varying(255),\
        geometry geometry,geomid character varying DEFAULT 'nz_1'::character varying,api_key character varying(255),\
        query_dictionary jsonb,geometry_col_name character varying(255),UNIQUE (source_name))"
    engine.execute(create_table)
    insert_query = "INSERT INTO apilinks (source_name,source_apis, url,region_name,query_dictionary,api_modified_date,geometry_col_name) \
    VALUES (%s,%s,%s,%s,%s,%s,%s);\
    UPDATE apilinks SET geometry =(SELECT geom FROM nz_polygons WHERE apilinks.geomid = nz_polygons.geomid)"
    engine.execute(insert_query, records)
except:
    pass
