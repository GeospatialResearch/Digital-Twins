# -*- coding: utf-8 -*-
"""Fetch REC data in New Zealand from NIWA using the ArcGIS REST API."""

import logging

import geopandas as gpd
import requests

from src.digitaltwin.arcgis_rest_api import fetch_arcgis_rest_api_data

log = logging.getLogger(__name__)


def fetch_rec_data_from_niwa(
        area_of_interest: gpd.GeoDataFrame = None,
        output_sr: int = None) -> gpd.GeoDataFrame:
    """
    Retrieve REC data in New Zealand from NIWA using the ArcGIS REST API.

    Parameters
    ----------
    area_of_interest : gpd.GeoDataFrame = None
        A GeoDataFrame representing the area of interest for data retrieval. If not provided, all data will be fetched.
    output_sr : int = None
        The EPSG code of the spatial reference system in which the requested data should be returned if no area of
        interest is provided.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the fetched REC data in New Zealand.
    """
    # URL for retrieving REC data from NIWA
    rec_api_url = "https://gis.niwa.co.nz/server/rest/services/HYDRO/Flood_Statistics_Henderson_Collins_V2/MapServer/2"
    # Retrieve REC data in New Zealand from NIWA using the ArcGIS REST API
    rec_data = fetch_arcgis_rest_api_data(rec_api_url, area_of_interest, output_sr)
    return rec_data


def fetch_backup_rec_data_from_niwa() -> gpd.GeoDataFrame:
    """
    Retrieve REC data in New Zealand from NIWA OpenData.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the fetched REC data in New Zealand.

    Raises
    -------
    RuntimeError
        If failed to fetch REC data.
    """
    # Log a message indicating the start of fetching process
    log.info("Fetching backup 'rec_data' from NIWA OpenData.")
    # URL for the GeoJSON REC data
    url = ("https://opendata.arcgis.com/api/v3/datasets/ae4316ef6bc842c4aed6a76b10b0c39e_2/downloads/data?"
           "format=geojson&spatialRefId=4326&where=1%3D1")
    # Send a GET request to the URL
    response = requests.get(url)
    # Check if the request was successful (status code 200)
    if response.status_code == 200:
        # Parse the JSON response
        geojson_data = response.json()
        # Convert GeoJSON data to GeoDataFrame
        rec_data = gpd.GeoDataFrame.from_features(geojson_data['features'])
        # Ensure consistent column naming convention by converting all column names to lowercase
        rec_data.columns = rec_data.columns.str.lower()
        # Move the 'geometry' column to the end, ensuring spatial columns are located at the end of database tables
        rec_data['geometry'] = rec_data.pop('geometry')
        # Log a message indicating successful fetching
        log.info("Successfully fetched backup 'rec_data' from NIWA OpenData.")
        return rec_data
    else:
        # Raise a RuntimeError if fetching failed
        raise RuntimeError("Failed to fetch backup 'rec_data' from NIWA OpenData.")
