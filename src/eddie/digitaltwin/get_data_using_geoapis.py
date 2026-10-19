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
This script provides the core, generic OGC WFS data provider, built on the 'geoapis' library's 'WfsQuery' class,
usable against any standards-compliant WFS endpoint without requiring a provider-specific subclass or API key.
"""

import logging
from typing import Optional
from urllib.parse import parse_qs, urlparse

from geoapis.vector import WfsQuery, WfsQueryBase
import geopandas as gpd

log = logging.getLogger(__name__)

# Tried in turn by geoapis when querying a layer, since the attribute name for a feature's geometry column varies
# between WFS services (see geoapis.vector.WfsQueryBase.GEOMETRY_NAMES for provider-specific values).
DEFAULT_GEOMETRY_NAMES = ["GEOMETRY", "geometry", "Shape", "shape"]


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


def resolve_wfs_fetch_crs(crs: int) -> int:
    """
    Determine the CRS to request data in from a WFS service via geoapis. geoapis writes the bounding box as
    (north, east), which is only correct for CRSs with that axis order (e.g. 2193, 4326). For other CRSs (e.g.
    UTM zones, polar stereographic), fetch in EPSG:4326 instead and reproject locally afterwards.

    Parameters
    ----------
    crs : int
        The desired output CRS code.

    Returns
    -------
    int
        'crs' itself if its axis order is (north, east), otherwise 4326.
    """
    axes = tuple(axis.direction for axis in gpd.GeoSeries(crs=crs).crs.axis_info)
    return crs if axes == ("north", "east") else 4326


def fetch_vector_data_using_geoapis(
        fetcher: WfsQueryBase,
        layer: str | int,
        crs: int) -> gpd.GeoDataFrame:
    """
    Run an already-constructed 'geoapis' WFS fetcher for the given layer, and clean and reproject the result.

    Parameters
    ----------
    fetcher : WfsQueryBase
        An already-constructed geoapis fetcher (e.g. 'WfsQuery', or a provider-specific subclass such as
        'geoapis.vector.Linz'), configured with the desired key, CRS and bounding polygon.
    layer : str | int
        The layer identifier/name to query on the fetcher's service.
    crs : int
        The coordinate reference system (CRS) code the returned data should be reprojected to.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the fetched vector data, or an empty GeoDataFrame if nothing was returned.
    """
    vector_data = fetcher.run(layer)
    # Check if vector_data is not None and is an instance of gpd.GeoDataFrame
    if vector_data is not None and isinstance(vector_data, gpd.GeoDataFrame):
        # Clean the fetched vector data and bring it into the requested CRS
        vector_data = clean_fetched_vector_data(vector_data).to_crs(crs)
    else:
        # Create an empty GeoDataFrame to indicate no returned vector data
        vector_data = gpd.GeoDataFrame()
    return vector_data


def fetch_generic_wfs_data(
        layer_id: str, # todo CHANGE THIS TO url
        bbox: Optional[gpd.GeoDataFrame],
        crs: int) -> gpd.GeoDataFrame:
    """
    Fetch vector data from any standards-compliant OGC WFS endpoint using 'geoapis.vector.WfsQuery', matching the
    provider registry's (layer_id, bbox, crs) -> GeoDataFrame signature. Requires no account or API key, unlike
    the provider-specific 'geoapis' based providers in the optional 'eddie.digitaltwin.nz_providers' module.

    Parameters
    ----------
    layer_id : str
        The WFS GetFeature endpoint URL for the layer, including the server base URL and a 'typeNames' (or
        'typeName') query parameter naming the layer, e.g. "https://example.com/geoserver/wfs?service=WFS&
        request=GetFeature&typeNames=namespace:layer".
    bbox : Optional[gpd.GeoDataFrame]
        A GeoDataFrame whose total bounds are used to restrict the request to a bounding box. None fetches all
        features in the layer.
    crs : int
        The EPSG code of the coordinate reference system the returned data should be in.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the fetched vector data, reprojected to 'crs'.

    Raises
    ------
    ValueError
        If the WFS layer name cannot be determined from 'layer_id' (no 'typeNames'/'typeName' query parameter).
    """
    parsed_url = urlparse(layer_id)
    query_params = parse_qs(parsed_url.query)
    layer_name = next(
        (query_params[key][0] for key in ("typeNames", "typeName", "TYPENAME") if key in query_params), None)
    if not layer_name:
        raise ValueError(
            f"Could not determine the WFS layer name from URL: '{layer_id}'. "
            "Expected a 'typeNames' (or 'typeName') query parameter."
        )
    # geoapis does not serve every CRS (e.g. UTM zones), so fetch in WGS84/2193 and reproject locally if needed
    fetch_crs = resolve_wfs_fetch_crs(crs)
    bounding_polygon = bbox.to_crs(fetch_crs) if bbox is not None else None
    fetcher = WfsQuery(
        key="",
        netloc_url=parsed_url.netloc,
        geometry_names=DEFAULT_GEOMETRY_NAMES,
        crs=fetch_crs,
        bounding_polygon=bounding_polygon,
        verbose=False,
    )
    log.info(f"Fetching geographic data from {layer_id} using OGC WFS (via geoapis).")
    vector_data = fetch_vector_data_using_geoapis(fetcher, layer_name, crs)
    log.info(f"Successfully fetched geographic data from {layer_id} using OGC WFS (via geoapis).")
    return vector_data
