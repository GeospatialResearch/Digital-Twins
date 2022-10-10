# -*- coding: utf-8 -*-
"""
@Script name: rainfall_data_from_hirds.py
@Description: Fetch rainfall data from the HIRDS website.
@Author: pkh35
@Date: 20/01/2022
@Last modified by: sli229
@Last modified date: 11/10/2022
"""

import requests
from requests.structures import CaseInsensitiveDict
import re
import pandas as pd
from typing import List, NamedTuple
from io import StringIO


def get_site_url_key(site_id: str, idf: bool) -> str:
    """
    Get the unique URL key of the requested rainfall site from the HIRDS website using curl commands.

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
    Fetch rainfall data for the requested rainfall site from the HIRDS website using curl commands.

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


class BlockStructure(NamedTuple):
    """
    Represents fetched rainfall data's layout structure.

    Attributes
    ----------
    skip_rows : int
        Number of lines to skip at the start of the fetched rainfall site_data.
    rcp : float
        There are four different representative concentration pathways (RCPs), and abbreviated as RCP2.6, RCP4.5,
        RCP6.0 and RCP8.5, in order of increasing radiative forcing by greenhouse gases, or nan for historical data.
    time_period : str
        Rainfall estimates for two future time periods (e.g. 2031-2050 or 2081-2100) for four RCPs, or None for
        historical data.
    category : str
        Historical data, Historical Standard Error or Projections (i.e. hist, hist_stderr or proj).
    """
    skip_rows: int
    rcp: float
    time_period: str
    category: str


def get_layout_structure_of_data(site_data: str) -> List[BlockStructure]:
    """
    Return a list of tuples (skip_rows, rcp, time_period, category) of the fetched rainfall data's layout structure.

    Parameters
    ----------
    site_data : str
        Fetched rainfall data text string from the HIRDS website for the requested rainfall site.
    """
    layout_structure = []
    # Read the site_data text string line by line with a for loop
    for index, line in enumerate(StringIO(site_data)):
        # Get lines that contain "(mm) ::" for depth data or "(mm/hr) ::" for intensity data
        if "(mm) ::" in line or "(mm/hr) ::" in line:
            # Add the row number to skip_rows list
            skip_rows = index + 1
            # Add the obtained rcp and time_period values to list
            rcp_result = re.search(r"(\d*\.\d*)", line)
            period_result = re.search(r"(\d{4}-\d{4})", line)
            if rcp_result is not None or period_result is not None:
                rcp = float(rcp_result[0])
                time_period = period_result[0]
            else:
                # When there are no rcp and time_period values (i.e. for historical data)
                # Add nan or None to list depending on data type
                rcp = float("nan")
                time_period = None
            # Assign category to list
            if "standard error" in line:
                category = "hist_stderr"
            elif "Historical Data" in line:
                category = "hist"
            else:
                category = "proj"
            layout_structure.append(BlockStructure(skip_rows, rcp, time_period, category))
    return layout_structure


def convert_to_tabular_data(
        site_data: str, site_id: str, block_structure: BlockStructure) -> pd.DataFrame:
    """
    Return the requested rainfall site data in Pandas DataFrame format.

    Parameters
    ----------
    site_data : str
        Fetched rainfall data text string from the HIRDS website for the requested rainfall site.
    site_id : str
        HIRDS rainfall site id.
    block_structure : BlockStructure
        Represents fetched rainfall data's layout structure.
    """
    skip_rows, rcp, time_period, category = block_structure
    rainfall_data = pd.read_csv(StringIO(site_data), skiprows=skip_rows, nrows=12)
    rainfall_data.insert(0, "site_id", site_id)
    rainfall_data.insert(1, "category", category)
    rainfall_data.insert(2, "rcp", rcp)
    rainfall_data.insert(3, "time_period", time_period)
    rainfall_data.columns = rainfall_data.columns.str.lower()
    return rainfall_data
