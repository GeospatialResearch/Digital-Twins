# -*- coding: utf-8 -*-
"""
Created on Fri Aug  6 09:23:01 2021

@author: pkh35
"""

import setup_environment
from api_values import api_records
engine = setup_environment.get_connection_from_profile(config_file_name="db_configure.yml")
record =api_records()

try:
    create_table = "CREATE TABLE IF NOT EXISTS public.apilinks(unique_id uuid NOT NULL DEFAULT uuid_generate_v4(),\
            source_name character varying(255),source_apis character varying(65535),\
            access_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,url character varying(67777),\
            api_modified_date date,region_name character varying(255),\
            geometry geometry,geomid character varying DEFAULT 'nz_1'::character varying,api_key character varying(255),\
            query_dictionary jsonb,geometry_col_name character varying(255),UNIQUE (source_name))"
    engine.execute(create_table)
        
    insert_query = "INSERT INTO apilinks (source_name,source_apis, url,region_name,query_dictionary,api_modified_date,geometry_col_name) \
        VALUES (%(source_name)s,%(source_apis)s,%(url)s,%(region_name)s,%(query_dictionary)s,%(api_modified_date)s,%(geometry_col_name)s);\
        UPDATE apilinks SET geometry =(SELECT geom FROM region_geometry WHERE apilinks.region_name = region_geometry.regc2018_1)"
    
    engine.execute(insert_query, record)
except Exception as error:
    print (error)
    print ("Exception TYPE:", type(error))

