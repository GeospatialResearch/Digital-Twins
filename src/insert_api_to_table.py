# -*- coding: utf-8 -*-
"""
Created on Mon Sep 13 14:13:34 2021

@author: pkh35
"""
from urllib.parse import urlparse, parse_qs
import json
import urllib
from datetime import datetime
from bs4 import BeautifulSoup
import requests
import validators
import tables
import setup_environment
import sqlalchemy

def extract_api_params(api):
    """to parse the api, to get the base url and params"""
    parsed_api = urlparse(api)
    params = parse_qs(parsed_api.query)
    base_url = urllib.parse.urlunparse(
        (parsed_api.scheme, parsed_api.netloc, parsed_api.path, "", "", ""))
    return json.dumps(params), base_url

def url_validator(url = None):
    """check if the url entered by the user is valid"""
    valid = validators.url(url)
    return url if valid else print(f"Invalid URL: {url}")

def api_data_modified_date(url=None):
    """to get the modified date of the data source"""
    try:
        content = requests.get(url)
        soup = BeautifulSoup(content.text, 'html.parser')
        url_update_date = soup.find(
            "th", text="Last updated").find_next_sibling("td").text
        def mdy_to_ymd(url_date):
            """to change the format of the date type variable"""
            return datetime.strptime(url_date, '%d %b %Y').strftime('%Y-%m-%d')
        url_update_date = mdy_to_ymd(url_update_date)
        return url_update_date
    except:
        pass

def insert_records(data_provider:str,source_name:str, api:str, url:str, region:str, geometry_column:str,YOUR_KEY):
    valid_url = url_validator(url)
    modified_date = api_data_modified_date(valid_url)
    query_dictionary, source_apis = extract_api_params(api)
    record = {
        "data_provider": data_provider,
        "source_name": source_name,
        "source_apis": source_apis,
        "url" :valid_url,
        "region_name": region,
        "query_dictionary": query_dictionary,
        "api_modified_date": modified_date,
        "geometry_col_name": geometry_column  
    }
    engine = setup_environment.get_connection_from_profile(config_file_name="test_configure.yml")
    
    # check if the region_geometry table exists in the database
    insp = sqlalchemy.inspect(engine)
    table_exist = insp.has_table("region_geometry", schema="public")
    if table_exist == False: 
        try: 
            # insert the api key from stas NZ data portal
            response_data = tables.region_geometry(key = YOUR_KEY)
            response_data.to_postgis('region_geometry', engine, index = True, if_exists = 'replace')
        except Exception as error:
            print ("An exception has occured:", error, type(error))
    else:
        pass
    
    try:
        Apilink = tables.Apilink
        dbsession = tables.dbsession()
        dbsession.sessionCreate(Apilink,engine)
        
        api_query = Apilink(data_provider = record['data_provider'],
            source_name=record['source_name'], 
            source_apis=record['source_apis'], url=record['url'],
            region_name=record['region_name'],
            api_modified_date=record['api_modified_date'],
            query_dictionary="record['query_dictionary']",
            geometry_col_name=record['geometry_col_name']) 
        dbsession.runQuery(engine,api_query)

        query = "UPDATE apilinks SET geometry =(SELECT geometry FROM region_geometry\
            WHERE region_geometry.regc2021_v1_00_name = apilinks.region_name)"
        engine.execute(query)
        
    except Exception as error:
        print ("An exception has occured:", error, type(error))
    

    