# -*- coding: utf-8 -*-
"""
This script provides functions to interact with ArcGIS REST API feature layers, generate query parameters, and
retrieve geographic data for a specified area of interest.
"""  # noqa: D400

import asyncio
import logging
from typing import List, Dict, Union, NamedTuple

import aiohttp
import geopandas as gpd
import pandas as pd
import requests

log = logging.getLogger(__name__)


class RecordCounts(NamedTuple):
    """
    Represents the record counts of the feature layer.

    Attributes
    ----------
    max_record_count : int
        The maximum number of records that will be returned per query.
    total_record_count : int
        The total number of records available in the feature layer.
    """

    max_record_count: int
    total_record_count: int


def get_feature_layer_record_counts(url: str) -> RecordCounts:
    """
    Retrieve the maximum and total record counts from the feature layer.

    Parameters
    ----------
    url : str
        The URL of the feature layer.

    Returns
    -------
    RecordCounts
        A named tuple containing the maximum and total record counts of the feature layer.

    Raises
    ------
    RuntimeError
        If there is an issue with retrieving the record counts from the feature layer.
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
    try:
        # Extract the total record count from the response
        total_record_count = response.json()["count"]
    except KeyError as e:
        # Raise a RuntimeError to indicate the API failure
        raise RuntimeError("Failed to get the feature layer record counts.") from e
    # Returns the maximum and total record counts of the feature layer
    return RecordCounts(max_record_count, total_record_count)


def gen_query_param_list(
        url: str,
        area_of_interest: gpd.GeoDataFrame = None,
        output_sr: int = None) -> List[Dict[str, Union[str, int]]]:
    """
    Generate a list of API query parameters used to retrieve ArcGIS REST API data.

    Parameters
    ----------
    url : str
        The URL of the feature layer.
    area_of_interest : gpd.GeoDataFrame = None
        A GeoDataFrame representing the area of interest for data retrieval. If not provided, all data will be fetched.
    output_sr : int = None
        The EPSG code of the spatial reference system in which the requested data should be returned if no area of
        interest is provided.

    Returns
    -------
    List[Dict[str, Union[str, int]]]
        A list of API query parameters used to retrieve ArcGIS REST API data.

    Raises
    ------
    ValueError
        If `output_sr` is provided when `area_of_interest` is given.
    """
    # If no area_of_interest is provided and output_sr is not specified, default output_sr to 2193
    if area_of_interest is None and output_sr is None:
        output_sr = 2193
    # Raise an error if output_sr is provided when area_of_interest is already given
    if area_of_interest is not None and output_sr is not None:
        raise ValueError("`output_sr` should not be provided when `area_of_interest` is given.")
    # Retrieves the maximum and total record counts from the feature layer
    max_record_count, total_record_count = get_feature_layer_record_counts(url)
    # Base query parameters used in each API call
    query_params_base = {
        "where": "1=1",
        "outFields": "*",
        "outSR": output_sr,
        "f": "geojson",
    }

    # Check if a specific area of interest (AOI) is provided
    if area_of_interest is not None:
        # Extract the bounding box coordinates from the area of interest
        x_min, y_min, x_max, y_max = area_of_interest.total_bounds
        # Create a string representation of the bounding box coordinates for use in the API query
        aoi_geom = f"{x_min},{y_min},{x_max},{y_max}"
        # Get the EPSG code of the Coordinate Reference System (CRS) of the area of interest
        aoi_crs = area_of_interest.crs.to_epsg()
        # Update the base query parameters with AOI-specific details
        query_params_base.update({
            "geometry": aoi_geom,
            "geometryType": "esriGeometryEnvelope",
            "inSR": aoi_crs,
            "spatialRel": "esriSpatialRelContains",
            "outSR": aoi_crs
        })

    # Initialize an empty list to hold all query parameters
    query_params_list = []
    # Iterate over the range of record offsets to generate query parameters in batches
    for offset in range(0, total_record_count, max_record_count):
        # Create a copy of the base query parameters for each batch
        query_params = query_params_base.copy()
        # Add the current offset to the query parameters
        query_params["resultOffset"] = offset
        # Append the query parameters for this batch to the list
        query_params_list.append(query_params)
    # Return the complete list of query parameters
    return query_params_list


async def _fetch_geo_data(
        session: aiohttp.ClientSession,
        url: str,
        query_param: Dict[str, Union[str, int]]) -> gpd.GeoDataFrame:
    """
    Fetch geographic data using the provided query parameters within a single API call.

    Parameters
    ----------
    session : aiohttp.ClientSession
        An instance of `aiohttp.ClientSession` used for making HTTP requests.
    url : str
        The URL of the feature layer.
    query_param : Dict[str, Union[str, int]]
        The query parameters used to retrieve geographic data.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the fetched geographic data.
    """
    # Construct the query URL for the REC feature layer
    query_url = f"{url}/query"
    # Send a GET request to the provided query URL with the query parameters
    async with session.get(query_url, params=query_param) as resp:
        # Parse the API response as JSON
        resp_json = await resp.json(content_type=None)
        # Convert the JSON response into a GeoDataFrame
        resp_gdf = gpd.GeoDataFrame.from_features(resp_json)
        return resp_gdf


async def fetch_geo_data_for_aoi(
        url: str,
        area_of_interest: gpd.GeoDataFrame = None,
        output_sr: int = None) -> gpd.GeoDataFrame:
    """
    Retrieve geographic data for the area of interest using the ArcGIS REST API.

    Parameters
    ----------
    url : str
        The URL of the feature layer.
    area_of_interest : gpd.GeoDataFrame = None
        A GeoDataFrame representing the area of interest for data retrieval. If not provided, all data will be fetched.
    output_sr : int = None
        The EPSG code of the spatial reference system in which the requested data should be returned if no area of
        interest is provided.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the fetched geographic data for the area of interest.
    """
    async with aiohttp.ClientSession() as session:
        # Generate a list of API query parameters used to retrieve data
        query_param_list = gen_query_param_list(url, area_of_interest, output_sr)
        # Create a list of tasks to fetch data for each query parameter
        tasks = [_fetch_geo_data(session, url, query_param) for query_param in query_param_list]
        # Wait for all tasks to complete and retrieve the results
        query_results = await asyncio.gather(*tasks, return_exceptions=True)
        # Concatenate the results into a single GeoDataFrame
        geo_data = gpd.GeoDataFrame(pd.concat(query_results, ignore_index=True))
        # Move the 'geometry' column to the last column
        geo_data['geometry'] = geo_data.pop('geometry')
        # Convert all column names to lowercase
        geo_data.columns = geo_data.columns.str.lower()
        # Get the unique EPSG code from the query parameters
        epsg_code = set(param['outSR'] for param in query_param_list).pop()
        # Apply the unique EPSG code as the CRS for geo_data
        geo_data.set_crs(epsg=epsg_code, inplace=True)
    return geo_data


def fetch_arcgis_rest_api_data(
        url: str,
        area_of_interest: gpd.GeoDataFrame = None,
        output_sr: int = None) -> gpd.GeoDataFrame:
    """
    Retrieve geographic data for the area of interest using the ArcGIS REST API.

    Parameters
    ----------
    url : str
        The URL of the feature layer.
    area_of_interest : gpd.GeoDataFrame = None
        A GeoDataFrame representing the area of interest for data retrieval. If not provided, all data will be fetched.
    output_sr : int = None
        The EPSG code of the spatial reference system in which the requested data should be returned if no area of
        interest is provided.

    Returns
    -------
    gpd.GeoDataFrame
         A GeoDataFrame containing the fetched geographic data for the area of interest.

    Raises
    ------
    RuntimeError
        If failed to fetch geographic data for the area of interest.
    """
    try:
        # Log the start of the data fetching process
        log.info(f"Fetching geographic data from {url} using the ArcGIS REST API.")
        # Fetch geographic data for the area of interest using the ArcGIS REST API
        geo_data = asyncio.run(fetch_geo_data_for_aoi(url, area_of_interest, output_sr))
        # Log the successful data retrieval
        log.info(f"Successfully fetched geographic data from {url} using the ArcGIS REST API.")
        return geo_data
    except TypeError as e:
        # Raise a RuntimeError to indicate the failure
        raise RuntimeError(f"Failed to fetch geographic data from {url} using the ArcGIS REST API.") from e
