# -*- coding: utf-8 -*-
"""
Created on Fri Aug 13 09:37:50 2021.

@author: pkh35, sli229
"""
from urllib.parse import urlparse
import geoapis.vector
import pandas as pd


def access_api_info(engine, source_name: tuple):
    """Get the rows which contains the requested sources from apilinks table in the database."""
    queries = engine.execute(
        "SELECT data_provider, source_name, layer, source_api, query_dictionary, geometry_col_name\
                             FROM apilinks WHERE source_name IN %(source_name)s",
        ({"source_name": source_name}),
    )
    api_record = []
    for query in queries:
        api_record.append(query)
    api_records = pd.DataFrame(
        api_record,
        columns=[
            "data_provider",
            "source_name",
            "layer",
            "source_api",
            "query_dictionary",
            "geometry_col_name",
        ],
    )
    return api_records


def data_from_apis(engine, key, base_url, layer, geometry_name, table_name, polygon):
    """Use geoapis module to request data from the stored apis."""
    base_url = urlparse(base_url)
    vector_fetcher = geoapis.vector.WfsQuery(
        key=key,
        netloc_url=base_url.netloc,
        geometry_names=geometry_name,
        bounding_polygon=polygon,
        verbose=True,
    )
    response_data = vector_fetcher.run(layer)
    try:
        response_data.to_postgis(table_name, engine, index=False, if_exists="append")
        # add unique_id column in each table
        engine.execute(
            'ALTER TABLE "%(table_name)s" ADD COLUMN IF NOT\
                            EXISTS unique_id SERIAL PRIMARY KEY'
            % ({"table_name": table_name})
        )
        # delete duplicate rows from the tables if exists
        engine.execute(
            'DELETE FROM "%(table_name)s" a USING "%(table_name)s"\
                       b WHERE a.unique_id < b.unique_id AND a.geometry = \
                           b.geometry;'
            % ({"table_name": table_name})
        )
    except Exception as error:
        print(error)
        print("No data available for the given polygon", table_name, type(error))


def get_source_from_db(engine, source_list):
    """Get the requested source data from the tables and return the pandas dataframe."""
    query = engine.execute(
        "SELECT source_name, api_modified_date FROM apilinks WHERE source_name IN %(source_list)s",
        ({"source_list": source_list}),
    )
    sources = []
    for source in query:
        sources.append(source)
    srcListUser_to_dict = pd.DataFrame(
        sources, columns=["source_name", "api_modified_date"]
    ).to_dict(orient="list")
    return srcListUser_to_dict
