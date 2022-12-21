# -*- coding: utf-8 -*-
"""
Created on Mon Sep 13 14:13:34 2021.

@author: pkh35, sli229
"""
import json
import logging
import urllib
from datetime import datetime
from urllib.parse import urlparse, parse_qs

import requests
import validators
from bs4 import BeautifulSoup

from src.digitaltwin import tables

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def region_geometry_table(engine, stats_nz_api_key):
    """Create region_geometry table which is used to create the geometry column
    in the apilinks table."""
    # create region_geometry table if it doesn't exist in the database
    try:
        response_data = tables.region_geometry(key=stats_nz_api_key)
        response_data.to_postgis(
            "region_geometry", engine, index=False, if_exists="fail"
        )
    except ValueError:
        log.info("Table 'region_geometry' already exists.")


def url_validator(url=None):
    """Check if the url entered by the user is valid."""
    valid = validators.url(url)
    if not valid:
        raise ValueError(f"Invalid URL: {url}")
    return url


def dmy_to_ymd(url_date):
    """To change the format of the date type variable."""
    return datetime.strptime(url_date, "%d %b %Y").strftime("%Y-%m-%d")


def api_data_modified_date(data_provider: str, url=None):
    """To get the modified date of the data source."""
    content = requests.get(url)
    soup = BeautifulSoup(content.text, "html.parser")
    if data_provider == "LINZ" or data_provider == "LRIS":
        url_update_date = (
            soup.find("th", text="Last updated").find_next_sibling("td").text
        )
    elif data_provider == "StatsNZ":
        url_update_date = soup.find("th", text="Added").find_next_sibling("td").text
    else:
        raise ValueError(f"{data_provider} not in ['LINZ', 'LRIS', 'StatsNZ']")
    try:
        url_update_date = dmy_to_ymd(url_update_date)
        return url_update_date
    except TypeError as e:
        raise TypeError(f"Invalid modified date of the data source {url} from data provider {data_provider}.") from e


def extract_api_params(api):
    """To parse the api, to get the base url and params."""
    parsed_api = urlparse(api)
    params = parse_qs(parsed_api.query)
    base_url = urllib.parse.urlunparse(
        (parsed_api.scheme, parsed_api.netloc, parsed_api.path, "", "", "")
    )
    return json.dumps(params), base_url


def insert_records(
    engine,
    data_provider: str,
    source_name: str,
    api: str,
    region_name: str,
    geometry_col_name: str = None,
    url=None,
    layer=None,
):
    """Insert user inputs as a row in the apilinks table."""
    if not source_name[0].isalpha() \
            and not source_name.startswith("_"):
        raise ValueError("source_name should start with _ or a letter")

    valid_url = url_validator(url)
    modified_date = api_data_modified_date(data_provider, valid_url)
    query_dictionary, source_api = extract_api_params(api)
    record = {
        "data_provider": data_provider,
        "source_name": source_name,
        "source_api": source_api,
        "url": valid_url,
        "region_name": region_name,
        "query_dictionary": query_dictionary,
        "api_modified_date": modified_date,
        "layer": layer,
        "geometry_col_name": geometry_col_name,
    }
    Apilink = tables.Apilink
    dbsession = tables.dbsession()
    dbsession.sessionCreate(Apilink, engine)

    api_query = Apilink(
        data_provider=record["data_provider"],
        source_name=record["source_name"],
        layer=record["layer"],
        region_name=record["region_name"],
        source_api=record["source_api"],
        api_modified_date=record["api_modified_date"],
        url=record["url"],
        query_dictionary=record["query_dictionary"],
        geometry_col_name=record["geometry_col_name"],
    )
    dbsession.runQuery(engine, api_query)
    # add geometry column from region_geometry table.
    query = "UPDATE apilinks SET geometry =\
    (SELECT geometry FROM region_geometry\
    WHERE region_geometry.regc2021_v1_00_name = apilinks.region_name)"
    engine.execute(query)
