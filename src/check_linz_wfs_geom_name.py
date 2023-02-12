# -*- coding: utf-8 -*-
"""
Created on Thu Jul 14 17:25:52 2022
@author: sli229

Used to fetch geometry column name from LINZ which is needed to fill the
 instructions_run.json file. User will need to specify the 'LINZ_layer' in
 order to get the geometry column name for the specified layer.
"""

import requests
from bs4 import BeautifulSoup

import config


def get_linz_wfs_geom_name(key, layer):
    """Fetch geometry column name from LINZ which is needed for WFS spatial data
    filtering."""
    URL = (
        f"https://data.linz.govt.nz/services;key={key}/wfs?service="
        f"WFS&version=2.0.0&request=DescribeFeatureType&typeNames={layer}"
    )
    response = requests.get(URL)
    soup = BeautifulSoup(response.content, features="xml")
    tag = soup.find("xsd:sequence").find_all("xsd:element")[-1]
    geom_col_name = tag.get("name")
    return geom_col_name


if __name__ == "__main__":
    linz_api_key = config.get_env_variable("LINZ_API_KEY")
    # Specify the required layer
    LINZ_layer = "layer-50327"
    # Get the geometry column name
    geom_col_name = get_linz_wfs_geom_name(linz_api_key, LINZ_layer)
    print(geom_col_name)
