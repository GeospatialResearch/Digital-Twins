# -*- coding: utf-8 -*-
"""
Created on Fri Aug  6 09:38:30 2021

@author: pkh35
"""

from urllib.parse import urlparse, parse_qs
import json
import pathlib
import urllib
from datetime import datetime
from bs4 import BeautifulSoup
import requests
import validators


def extract_api_params(api):
    """to parse the api, to get the base url and params"""
    parsed_api = urlparse(api)
    params = parse_qs(parsed_api.query)
    base_url = urllib.parse.urlunparse(
        (parsed_api.scheme, parsed_api.netloc, parsed_api.path, "", "", ""))
    return json.dumps(params), base_url

def url_validator(url):
    """check if the url entered by the user is valid"""
    valid = validators.url(url)
    return url if valid is True else print("Invalid url")

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
    
def api_records():
    # load in the instructions
    file_path = pathlib.Path().cwd() / pathlib.Path("instructions_new.json")
    with open(file_path, 'r') as file_pointer:
            instructions = json.load(file_pointer)
            
    source_names = instructions['instructions']['apis']['linz']['source_name']
    region_name = instructions['instructions']['region_name']
    geometry_col_name = instructions['instructions']['apis']['linz']['geometry_col_name']
    url = instructions['instructions']['url']
    api = instructions['instructions']['api']
    valid_url = url_validator(url)
    modified_date = api_data_modified_date(valid_url)
    query_dictionary, source_apis = extract_api_params(api)
    record = {
        "source_name": source_names,
        "source_apis": source_apis,
        "url" :valid_url,
        "region_name": region_name,
        "query_dictionary": query_dictionary,
        "api_modified_date": modified_date,
        "geometry_col_name": geometry_col_name  
    }

    return record

