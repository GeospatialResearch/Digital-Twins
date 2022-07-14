# -*- coding: utf-8 -*-
"""
Created on Mon Sep 13 14:13:34 2021.

@author: pkh35
"""
import json
import urllib
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import requests
import sqlalchemy
import validators
from bs4 import BeautifulSoup
from . import tables


def extract_api_params(api):
    """To parse the api, to get the base url and params."""
    parsed_api = urlparse(api)
    params = parse_qs(parsed_api.query)
    base_url = urllib.parse.urlunparse(
        (parsed_api.scheme, parsed_api.netloc, parsed_api.path, "", "", ""))
    return json.dumps(params), base_url


def url_validator(url=None):
    """Check if the url entered by the user is valid."""
    valid = validators.url(url)
    return url if valid else print(f"Invalid URL: {url}")


def mdy_to_ymd(url_date):
    """To change the format of the date type variable."""
    return datetime.strptime(url_date, '%d %b %Y').strftime('%Y-%m-%d')


def api_data_modified_date(data_provider: str, url=None):
    """To get the modified date of the data source."""
    try:
        content = requests.get(url)
        soup = BeautifulSoup(content.text, 'html.parser')
        if data_provider == 'LINZ' or data_provider == 'LRIS':
            url_update_date = soup.find(
                "th", text="Last updated").find_next_sibling("td").text
        elif data_provider == 'StatsNZ':
            url_update_date = soup.find(
                "th", text="Added").find_next_sibling("td").text
        else:
            return None
        url_update_date = mdy_to_ymd(url_update_date)
        return url_update_date
    except Exception as error:
        print(error, type(error))
    finally:
        pass


def region_geometry_table(engine, YOUR_KEY):
    """Create region_geometry table which is used to create the geometry column in the apilinks table."""
    # check if the region_geometry table exists in the database
    insp = sqlalchemy.inspect(engine)
    table_exist = insp.has_table("region_geometry", schema="public")
    if table_exist is False:
        try:
            # insert the api key from stas NZ data portal
            response_data = tables.region_geometry(key=YOUR_KEY)
            response_data.to_postgis('region_geometry', engine, index=True,
                                     if_exists='replace')
        except Exception as error:
            print(error, type(error))
    else:
        print('region_geometry table exists')


def insert_records(engine, data_provider: str, source_name: str, api: str, region: str,
                   geometry_column: str = None, url=None, layer=None):
    """Insert user inputs as a row in the apilinks table."""
    if source_name[0].isalpha() or source_name[0].startswith("_"):
        valid_url = url_validator(url)
        modified_date = api_data_modified_date(data_provider, valid_url)
        query_dictionary, source_apis = extract_api_params(api)
        record = {
            "data_provider": data_provider,
            "source_name": source_name,
            "source_apis": source_apis,
            "url": valid_url,
            "region_name": region,
            "query_dictionary": query_dictionary,
            "api_modified_date": modified_date,
            "layer": layer,
            "geometry_col_name": geometry_column
        }
        try:
            Apilink = tables.Apilink
            dbsession = tables.dbsession()
            dbsession.sessionCreate(Apilink, engine)

            api_query = Apilink(
                data_provider=record['data_provider'],
                source_name=record['source_name'],
                source_apis=record['source_apis'],
                url=record['url'],
                region_name=record['region_name'],
                api_modified_date=record['api_modified_date'],
                query_dictionary=record['query_dictionary'],
                layer=record['layer'],
                geometry_col_name=record['geometry_col_name'])
            dbsession.runQuery(engine, api_query)
            # add geomerty column from region_geomerty table.
            query = "UPDATE apilinks SET geometry =(SELECT geometry FROM\
                region_geometry WHERE region_geometry.regc2021_v1_00_name\
                    = apilinks.region_name)"
            engine.execute(query)

        except Exception as error:
            print(error, type(error))
    else:
        print("source_name should start with _ or a letter")
