# -*- coding: utf-8 -*-
"""
Fetch REC1 data in New Zealand from NIWA using the ArcGIS REST API.
"""

from typing import Tuple, List, Dict, Union
import asyncio

import aiohttp
import requests
import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString
from sqlalchemy.engine import Engine

from src.digitaltwin.utils import get_nz_boundary

# URL for retrieving REC1 data from NIWA using the ArcGIS REST API
REC1_API_URL = "https://gis.niwa.co.nz/server/rest/services/HYDRO/Flood_Statistics_Henderson_Collins_V2/MapServer/2"


def get_feature_layer_record_counts(url: str = REC1_API_URL) -> Tuple[int, int]:
    """
    Retrieves the maximum and total record counts from the REC1 feature layer.

    Parameters
    ----------
    url : str = REC1_API_URL
        The URL of the REC1 feature layer. Defaults to 'REC1_API_URL'.

    Returns
    -------
    Tuple[int, int]
        A tuple of integers containing the maximum record count and the total record count.
        - max_record_count (int): The maximum number of records that will be returned per query.
        - total_record_count (int): The total number of records available in the feature layer.
    """
    # Set up parameters for the initial request to get the maximum record count
    params = {"f": "json"}
    response = requests.get(url=url, params=params)
    # Extract the maximum record count from the response
    max_record_count = response.json()["maxRecordCount"]
    # Set up parameters for the second request to get the total record count
    params["where"] = "1=1"
    params["returnCountOnly"] = True
    response = requests.get(url=f"{url}/query", params=params)
    # Extract the total record count from the response
    total_record_count = response.json()["count"]
    # Return a tuple containing the max and total record counts
    return max_record_count, total_record_count


def gen_api_query_param_list(
        engine: Engine,
        max_record_count: int,
        total_record_count: int) -> List[Dict[str, Union[str, int]]]:
    """
    Generate a list of API query parameters used to retrieve REC1 data in New Zealand.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    max_record_count : int
        The maximum number of records that will be returned per query.
    total_record_count : int
        The total number of records available in the feature layer.

    Returns
    -------
    List[Dict[str, Union[str, int]]]
        A list of API query parameters used to retrieve REC1 data in New Zealand.
    """
    # Get the New Zealand boundary geometry in the specified CRS
    nz_boundary = get_nz_boundary(engine, to_crs=2193)
    # Extract the bounding box coordinates from the New Zealand boundary
    x_min, y_min, x_max, y_max = nz_boundary.total_bounds
    # Create a string representation of the bounding box coordinates for use in the API query
    nz_geometry = f"{x_min},{y_min},{x_max},{y_max}"

    # Initialize an empty list to store query parameters
    query_param_list = []
    # Use a while loop to generate query parameters in batches
    result_offset = 0
    while result_offset < total_record_count:
        # Define the query parameters for the current batch
        query_params = {
            "where": "1=1",
            "outFields": "*",
            "geometry": nz_geometry,
            "geometryType": "esriGeometryEnvelope",
            "inSR": 2193,
            "spatialRel": "esriSpatialRelContains",
            "outSR": 2193,
            "f": "json",
            "resultOffset": result_offset
        }
        # Append the current batch of query parameters to the list
        query_param_list.append(query_params)
        # Increment 'result_offset' for the next batch
        result_offset += max_record_count
    # Return the list of query parameters
    return query_param_list


async def fetch_rec1_data(
        session: aiohttp.ClientSession,
        query_param: Dict[str, Union[str, int]],
        url: str = f"{REC1_API_URL}/query") -> gpd.GeoDataFrame:
    """
    Fetch REC1 data using the provided query parameters within a single API call.

    Parameters
    ----------
    session : aiohttp.ClientSession
        An instance of `aiohttp.ClientSession` used for making HTTP requests.
    query_param : Dict[str, Union[str, int]]
        The query parameters used to retrieve REC1 data.
    url : str = REC1_API_URL
        The query URL of the REC1 feature layer.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the fetched REC1 data.
    """
    # Send a GET request to the provided query URL with the query parameters
    async with session.get(url, params=query_param) as resp:
        # Process the response as JSON
        resp_dict = await resp.json(content_type=None)
        # Extract the features from the response
        features = resp_dict["features"]
        # Create a Pandas DataFrame from the attributes of each feature in the response
        rec1_features = pd.DataFrame([feature['attributes'] for feature in features])
        # Extract the geometries from the response and create a list of LineString objects
        rec1_geometries = [LineString(feature['geometry']['paths'][0]) for feature in features]
        # Create a GeoDataFrame with REC1 features and geometries, with specified CRS
        rec1_gdf = gpd.GeoDataFrame(rec1_features, geometry=rec1_geometries, crs=resp_dict['spatialReference']['wkid'])
        # Return the GeoDataFrame containing REC1 data
        return rec1_gdf


async def fetch_rec1_data_for_nz(
        query_param_list: List[Dict[str, Union[str, int]]],
        url: str = REC1_API_URL) -> gpd.GeoDataFrame:
    """
    Iterate over the list of API query parameters to fetch REC1 data in New Zealand.

    Parameters
    ----------
    query_param_list : List[Dict[str, Union[str, int]]]
        A list of API query parameters used to retrieve REC1 data in New Zealand.
    url : str = REC1_API_URL
        The URL of the REC1 feature layer. Defaults to 'REC1_API_URL'.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the fetched REC1 data in New Zealand.
    """
    async with aiohttp.ClientSession() as session:
        # Construct the query URL for the REC1 feature layer
        query_url = f"{url}/query"
        # Create a list of tasks to fetch REC1 data for each query parameter
        tasks = [fetch_rec1_data(session, query_param, query_url) for query_param in query_param_list]
        # Wait for all tasks to complete and retrieve the results
        query_results = await asyncio.gather(*tasks, return_exceptions=True)
        # Concatenate the results into a single GeoDataFrame
        rec1_data = gpd.GeoDataFrame(pd.concat(query_results))
        # Convert all column names to lowercase
        rec1_data.columns = rec1_data.columns.str.lower()
        # Remove duplicate records based on the 'objectid' column, preserving the first occurrence
        rec1_data = rec1_data.drop_duplicates(subset='objectid', keep='first')
        # Sort the GeoDataFrame by the 'objectid' column and reset the index
        rec1_data = rec1_data.sort_values(by=['objectid']).reset_index(drop=True)
    return rec1_data


def fetch_rec1_data_from_niwa(engine: Engine, url: str = REC1_API_URL) -> gpd.GeoDataFrame:
    """
    Retrieve REC1 data in New Zealand from NIWA using the ArcGIS REST API.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    url : str = REC1_API_URL
        The URL of the REC1 feature layer. Defaults to 'REC1_API_URL'.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the fetched REC1 data in New Zealand.
    """
    # Retrieves the maximum and total record counts from the REC1 feature layer
    max_record_count, total_record_count = get_feature_layer_record_counts(url)
    # Generate a list of API query parameters used to retrieve REC1 data in New Zealand
    query_param_list = gen_api_query_param_list(engine, max_record_count, total_record_count)
    # Iterate over the list of API query parameters to fetch REC1 data in New Zealand
    rec1_data = asyncio.run(fetch_rec1_data_for_nz(query_param_list, url))
    return rec1_data
