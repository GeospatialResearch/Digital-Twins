# -*- coding: utf-8 -*-
"""
This script provides functions to retrieve vector data from multiple providers, including StatsNZ, LINZ, and MFE,
using the 'geoapis' library. To access data from each provider, you'll need to set an
API key in the environment variables.
"""

from typing import Optional

import geopandas as gpd
from geoapis.vector import StatsNz, Linz, WfsQueryBase

from src.config import EnvVariable


class MFE(WfsQueryBase):
    """A class to manage fetching Vector data from MFE.

    General details at: https://data.mfe.govt.nz/
    API details at: https://help.koordinates.com/

    Note that the 'GEOMETRY_NAMES' used when making WFS 'cql_filter' queries varies between layers.
    The MFE generally follows the LINZ LDS but uses 'Shape' in place of 'shape'. It still uses 'GEOMETRY'.
    """

    NETLOC_API = "data.mfe.govt.nz"
    GEOMETRY_NAMES = ["GEOMETRY", "Shape"]


def clean_fetched_vector_data(fetched_data: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Clean the fetched vector data by performing necessary transformations.

    Parameters
    ----------
    fetched_data : gpd.GeoDataFrame
        A GeoDataFrame containing the fetched vector data.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the cleaned vector data.
    """
    # Ensure consistent column naming convention by converting all column names to lowercase
    fetched_data.columns = fetched_data.columns.str.lower()
    # Move the 'geometry' column to the end, ensuring spatial columns are located at the end of database tables
    fetched_data['geometry'] = fetched_data.pop('geometry')
    return fetched_data


def fetch_vector_data_using_geoapis(
        data_provider: str,
        layer_id: int,
        crs: int = 2193,
        verbose: bool = False,
        bounding_polygon: Optional[gpd.GeoDataFrame] = None) -> gpd.GeoDataFrame:
    """
    Fetch vector data using 'geoapis' based on the specified data provider, layer ID, and other parameters.

    Parameters
    -----------
    data_provider : str
        The data provider to use. Supported values: "StatsNZ", "LINZ", "MFE".
    layer_id : int
        The ID of the layer to fetch.
    crs : int = 2193
        The coordinate reference system (CRS) code to use. Default is 2193.
    verbose : bool = False
        Whether to print messages. Default is False.
    bounding_polygon : Optional[gpd.GeoDataFrame] = None
        Bounding polygon for data fetching. Default is all of New Zealand.

    Returns
    --------
    gpd.GeoDataFrame
        A GeoDataFrame containing the fetched vector data.

    Raises
    -------
    ValueError
        If an unsupported 'data_provider' value is provided.
    """
    # Determine the appropriate vector fetcher based on the data provider
    if data_provider == "StatsNZ":
        stats_nz_api_key = EnvVariable.STATSNZ_API_KEY
        vector_fetcher = StatsNz(key=stats_nz_api_key, crs=crs, bounding_polygon=bounding_polygon, verbose=verbose)
    elif data_provider == "LINZ":
        linz_api_key = EnvVariable.LINZ_API_KEY
        vector_fetcher = Linz(key=linz_api_key, crs=crs, bounding_polygon=bounding_polygon, verbose=verbose)
    elif data_provider == "MFE":
        mfe_api_key = EnvVariable.MFE_API_KEY
        vector_fetcher = MFE(key=mfe_api_key, crs=crs, bounding_polygon=bounding_polygon, verbose=verbose)
    else:
        raise ValueError(f"Unsupported data_provider: {data_provider}")

    # Fetch the vector data using the determined vector fetcher
    vector_data = vector_fetcher.run(layer_id)
    # Check if vector_data is not None and is an instance of gpd.GeoDataFrame
    if vector_data is not None and isinstance(vector_data, gpd.GeoDataFrame):
        # Clean the fetched vector data
        vector_data = clean_fetched_vector_data(vector_data)
    else:
        # Create an empty GeoDataFrame to indicate no returned vector data
        vector_data = gpd.GeoDataFrame()
    return vector_data
