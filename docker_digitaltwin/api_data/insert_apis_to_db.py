# -*- coding: utf-8 -*-
"""
Created on Mon Sep  6 10:49:19 2021

@author: pkh35
"""

import sqlalchemy

import setup_environment
import tables
from api_values import api_records


def main():
    engine = setup_environment.get_connection_from_profile(config_file_name="db_configure.yml")
    record = api_records()

    # check if the region_geometry table exists in the database
    insp = sqlalchemy.inspect(engine)
    table_exist = insp.has_table("region_geometry", schema="public")
    if table_exist == False:
        try:
            # insert the api key from stas NZ data portal
            response_data = tables.region_geometry(key=YOUR_KEY)
            response_data.to_postgis('region_geometry', engine, index=True, if_exists='replace')
        except Exception as error:
            print("An exception has occured:", error, type(error))
    else:
        pass

    try:
        Apilink = tables.Apilink
        dbsession = tables.dbsession()
        dbsession.sessionCreate(Apilink, engine)

        api_query = Apilink(source_name=record['source_name'], \
                            source_apis=record['source_apis'], url=record['url'], \
                            region_name=record['region_name'], api_modified_date=record['api_modified_date'], \
                            query_dictionary="record['query_dictionary']", \
                            geometry_col_name=record['geometry_col_name'])
        dbsession.runQuery(engine, api_query)

        query = "UPDATE apilinks SET geometry =(SELECT geometry FROM region_geometry WHERE region_geometry.regc2021_v1_00_name = apilinks.region_name)"
        engine.execute(query)

    except Exception as error:
        print("An exception has occured:", error, type(error))


if __name__ == "__main__":
    main()
