# -*- coding: utf-8 -*-
"""
Created on Thu Jan 20 14:35:08 2022.

@author: pkh35
"""

import requests
from requests.structures import CaseInsensitiveDict
import pandas as pd


def get_url_id(site_id: str) -> str:
    """Each site has a unique key that need to be inserted in the url before making an api request."""
    url = "https://api.niwa.co.nz/hirds/report"
    headers = CaseInsensitiveDict()
    headers["Connection"] = "keep-alive"
    headers["sec-ch-ua"] = '"" Not A;Brand";v="99", "Chromium";v="96", "Google Chrome";v="96""'
    headers["Accept"] = "application/json, text/plain, */*"
    headers["Content-Type"] = "application/json"
    headers["sec-ch-ua-mobile"] = "?0"
    headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)\
        Chrome/96.0.4664.110 Safari/537.36"
    headers["sec-ch-ua-platform"] = '""Windows""'
    headers["Origin"] = "https://hirds.niwa.co.nz"
    headers["Sec-Fetch-Site"] = "same-site"
    headers["Sec-Fetch-Mode"] = "cors"
    headers["Sec-Fetch-Dest"] = "empty"
    headers["Referer"] = "https://hirds.niwa.co.nz/"
    headers["Accept-Language"] = "en-GB,en-US;q=0.9,en;q=0.8"
    data = f'{{"site_id":"{site_id}","idf":false}}'
    try:
        resp = requests.post(url, headers=headers, data=data)
    except requests.exceptions.HTTPError as error:
        print("Request Failed", error)
    hirds = pd.read_json(resp.text)  # get each sites url.
    site_url = hirds['url'][0]
    start = site_url.find("/asset/") + len("/asset/")
    # get the long digits part from the url
    site_id_url = site_url[start:]
    site_id_url = site_id_url.rsplit('/')[0]
    return site_id_url


def add_hirds_data_to_csv(site_id: str, response, path):
    """Store the depth data in the form of csv file in the desired path."""
    filename = fr'{path}\{site_id}_depth.csv'
    site_info = open(filename, "w")
    site_info.write(response)
    site_info.close()


def get_data_from_hirds(site_id: str, path: str):
    """Get data from the hirds website using curl command and store as a csv files."""
    site_id_url = get_url_id(site_id)
    url = f"https://api.niwa.co.nz/hirds/report/{site_id_url}/export"
    headers = CaseInsensitiveDict()
    headers["Connection"] = "keep-alive"
    headers["sec-ch-ua"] = '"" Not A;Brand";v="99", "Chromium";v="96", "Google Chrome";v="96""'
    headers["Accept"] = "application/json, text/plain, */*"
    headers["sec-ch-ua-mobile"] = "?0"
    headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)\
        Chrome/96.0.4664.110 Safari/537.36"
    headers["sec-ch-ua-platform"] = '""Windows""'
    headers["Origin"] = "https://hirds.niwa.co.nz"
    headers["Sec-Fetch-Site"] = "same-site"
    headers["Sec-Fetch-Mode"] = "cors"
    headers["Sec-Fetch-Dest"] = "empty"
    headers["Referer"] = "https://hirds.niwa.co.nz/"
    headers["Accept-Language"] = "en-GB,en-US;q=0.9,en;q=0.8"
    try:
        response = requests.get(url, headers=headers)
    except requests.exceptions.HTTPError as error:
        print("Request Failed", error)
    hirds_data = response.text
    add_hirds_data_to_csv(site_id, hirds_data, path)
