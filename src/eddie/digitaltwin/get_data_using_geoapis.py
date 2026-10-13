# -*- coding: utf-8 -*-
# Copyright © 2021-2026 Geospatial Research Institute Toi Hangarau
# LICENSE: https://github.com/GeospatialResearch/Digital-Twins/blob/master/LICENSE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
This script provides functions to retrieve vector data from multiple providers, including StatsNZ, LINZ, and MFE,
using the 'geoapis' library. To access data from each provider, you'll need to set an
API key in the environment variables.
"""

import logging
from typing import Optional

from geoapis.vector import Linz, StatsNz, WfsQueryBase
import geopandas as gpd

from eddie import config

log = logging.getLogger(__name__)


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
    fetched_data = fetched_data.rename(columns=str.lower)
    # Move the 'geometry' column to the end, ensuring spatial columns are located at the end of database tables.
    # Selecting columns keeps it a GeoDataFrame with its CRS, which pop() and re-assigning does not.
    return fetched_data[[column for column in fetched_data.columns if column != "geometry"] + ["geometry"]]


def fetch_vector_data_using_geoapis(
        data_provider: str,
        layer_id: int,
        crs: int,
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
    crs : int
        The coordinate reference system (CRS) code to use.
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
    OSError
        If the provider request fails for any reason other than an unsupported CRS (requests.HTTPError).
    """
    # The providers do not serve every CRS (e.g. UTM zones), so fetch in WGS84 and reproject locally
    wgs84 = 4326
    if bounding_polygon is not None:
        bounding_polygon = bounding_polygon.to_crs(wgs84)
    # Determine the appropriate vector fetcher based on the data provider
    providers = {
        "StatsNZ": (StatsNz, config.EnvVariable.STATSNZ_API_KEY),
        "LINZ": (Linz, config.EnvVariable.LINZ_API_KEY),
        "MFE": (MFE, config.EnvVariable.MFE_API_KEY),
    }
    if data_provider not in providers:
        raise ValueError(f"Unsupported data_provider: {data_provider}")
    fetcher_class, api_key = providers[data_provider]

    # geoapis writes the bounding box as (north, east), which is only right for CRSs with that axis order (e.g. 2193,
    # 4326). Fetch other CRSs (e.g. UTM zones, polar stereographic) in EPSG:4326 and reproject locally.
    axes = tuple(axis.direction for axis in gpd.GeoSeries(crs=crs).crs.axis_info)
    fetch_crs = crs if axes == ("north", "east") else 4326
    if bounding_polygon is not None:
        bounding_polygon = bounding_polygon.to_crs(fetch_crs)
    vector_data = fetcher_class(key=api_key, crs=fetch_crs, bounding_polygon=bounding_polygon, verbose=verbose).run(
        layer_id)
    # Check if vector_data is not None and is an instance of gpd.GeoDataFrame
    if vector_data is not None and isinstance(vector_data, gpd.GeoDataFrame):
        # Clean the fetched vector data and bring it into the requested CRS
        vector_data = clean_fetched_vector_data(vector_data).to_crs(crs)
    else:
        # Create an empty GeoDataFrame to indicate no returned vector data
        vector_data = gpd.GeoDataFrame()
    return vector_data
