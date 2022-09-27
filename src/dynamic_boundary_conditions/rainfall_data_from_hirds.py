# -*- coding: utf-8 -*-
"""
@Script name: rainfall_data_from_hirds.py
@Description: Fetch rainfall data from the HIRDS website.
@Author: pkh35
@Date: 20/01/2022
@Last modified by: sli229
@Last modified date: 27/09/2022
"""

import requests
from requests.structures import CaseInsensitiveDict
import re
import pandas as pd
import pathlib
from src.dynamic_boundary_conditions import hirds_rainfall_data_to_db


def get_site_url_key(site_id: str, idf: bool) -> str:
    """
    Get each rainfall sites' unique url key from the HIRDS website using curl commands.

    Parameters
    ----------
    site_id : str
        HIRDS rainfall site id.
    idf : bool
        Set to False for rainfall depth data, and True for rainfall intensity data.
    """
    url = "https://api.niwa.co.nz/hirds/report"
    headers = CaseInsensitiveDict()
    headers["Accept"] = "application/json, text/plain, */*"
    headers["Accept-Language"] = "en-GB,en-US;q=0.9,en;q=0.8"
    headers["Connection"] = "keep-alive"
    headers["Content-Type"] = "application/json"
    headers["Origin"] = "https://hirds.niwa.co.nz"
    headers["Referer"] = "https://hirds.niwa.co.nz/"
    headers["Sec-Fetch-Dest"] = "empty"
    headers["Sec-Fetch-Mode"] = "cors"
    headers["Sec-Fetch-Site"] = "same-site"
    headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)\
        Chrome/96.0.4664.110 Safari/537.36"
    headers["sec-ch-ua"] = '"" Not A;Brand";v="99", "Chromium";v="96", "Google Chrome";v="96""'
    headers["sec-ch-ua-mobile"] = "?0"
    headers["sec-ch-ua-platform"] = '""Windows""'
    idf = str(idf).lower()
    data = f'{{"site_id":"{site_id}","idf":{idf}}}'
    resp = requests.post(url, headers=headers, data=data)
    rainfall_results = pd.read_json(resp.text)
    # Get requested sites url unique key
    site_url = rainfall_results["url"][0]
    pattern = re.compile(r"(?<=/asset/)\w*(?=/)")
    site_url_key = re.findall(pattern, site_url)[0]
    return site_url_key


def get_data_from_hirds(site_id: str, idf: bool) -> str:
    """
    Get rainfall data from the HIRDS website using curl command.

    Parameters
    ----------
    site_id : str
        HIRDS rainfall site id.
    idf : bool
        Set to False for rainfall depth data, and True for rainfall intensity data.
    """
    site_url_key = get_site_url_key(site_id, idf)
    url = rf"https://api.niwa.co.nz/hirds/report/{site_url_key}/export"
    headers = CaseInsensitiveDict()
    headers["Accept"] = "application/json, text/plain, */*"
    headers["Accept-Language"] = "en-GB,en-US;q=0.9,en;q=0.8"
    headers["Connection"] = "keep-alive"
    headers["Origin"] = "https://hirds.niwa.co.nz"
    headers["Referer"] = "https://hirds.niwa.co.nz/"
    headers["Sec-Fetch-Dest"] = "empty"
    headers["Sec-Fetch-Mode"] = "cors"
    headers["Sec-Fetch-Site"] = "same-site"
    headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)\
        Chrome/96.0.4664.110 Safari/537.36"
    headers["sec-ch-ua"] = '"" Not A;Brand";v="99", "Chromium";v="96", "Google Chrome";v="96""'
    headers["sec-ch-ua-mobile"] = "?0"
    headers["sec-ch-ua-platform"] = '""Windows""'
    resp = requests.get(url, headers=headers)
    site_data = resp.text
    return site_data


def store_data_to_csv(site_id: str, file_path_to_store, idf: bool):
    """
    Store the rainfall data in the form of CSV file in the desired path.

    Parameters
    ----------
    site_id : str
        HIRDS rainfall site id.
    file_path_to_store
        The file path used to store the downloaded rainfall data CSV file.
    idf : bool
        Set to False for rainfall depth data, and True for rainfall intensity data.
    """
    if not pathlib.Path.exists(file_path_to_store):
        file_path_to_store.mkdir(parents=True, exist_ok=True)

    rain_table_name = hirds_rainfall_data_to_db.db_rain_table_name(idf)
    filename = pathlib.Path(f"{site_id}_{rain_table_name}.csv")
    site_data = get_data_from_hirds(site_id, idf)
    with open(file_path_to_store / filename, "w") as file:
        file.write(site_data)
