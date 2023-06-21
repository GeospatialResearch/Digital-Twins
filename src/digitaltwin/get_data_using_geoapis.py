# -*- coding: utf-8 -*-
"""
@Date: 17/06/2023
@Author: sli229
"""

from typing import Optional

import geopandas as gpd
from geoapis.vector import StatsNz, Linz, Lris, WfsQueryBase

from src import config


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
        The fetched vector data as a GeoDataFrame.

    Returns
    -------
    gpd.GeoDataFrame
        The cleaned vector data as a GeoDataFrame.
    """
    # Convert column names to lowercase
    fetched_data.columns = fetched_data.columns.str.lower()
    # Move 'geometry' column to the end
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

    Parameters:
    -----------
    data_provider : str
        The data provider to use. Supported values: "StatsNZ", "LINZ", "LRIS", "MFE".
    layer_id : int
        The ID of the layer to fetch.
    crs : int, optional
        The coordinate reference system (CRS) code to use. Default is 2193.
    verbose : bool, optional
        Whether to print messages. Default is False.
    bounding_polygon : gpd.GeoDataFrame, optional
        Bounding polygon for data fetching. Default is all of New Zealand.

    Returns:
    --------
    gpd.GeoDataFrame
        The fetched vector data as a GeoDataFrame.

    Raises:
    -------
    ValueError
        If an unsupported data_provider value is provided.
    """
    # Determine the appropriate vector fetcher based on the data provider
    if data_provider == "StatsNZ":
        stats_nz_api_key = config.get_env_variable("StatsNZ_API_KEY")
        vector_fetcher = StatsNz(key=stats_nz_api_key, crs=crs, bounding_polygon=bounding_polygon, verbose=verbose)
    elif data_provider == "LINZ":
        linz_api_key = config.get_env_variable("LINZ_API_KEY")
        vector_fetcher = Linz(key=linz_api_key, crs=crs, bounding_polygon=bounding_polygon, verbose=verbose)
    elif data_provider == "LRIS":
        lris_api_key = config.get_env_variable("LRIS_API_KEY")
        vector_fetcher = Lris(key=lris_api_key, crs=crs, bounding_polygon=bounding_polygon, verbose=verbose)
    elif data_provider == "MFE":
        mfe_api_key = config.get_env_variable("MFE_API_KEY")
        vector_fetcher = MFE(key=mfe_api_key, crs=crs, bounding_polygon=bounding_polygon, verbose=verbose)
    else:
        raise ValueError(f"Unsupported data_provider: {data_provider}")

    # Fetch the vector data using the determined vector fetcher
    vector_data = vector_fetcher.run(layer_id)
    # Clean the fetched vector data
    vector_data = clean_fetched_vector_data(vector_data)
    return vector_data
