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
This script provides a generic OGC WFS (Web Feature Service) data provider, usable against any standards-compliant
WFS endpoint. It requires no provider-specific account or API key, unlike the 'geoapis' based providers in the
optional 'eddie[nz]' extra ('eddie.digitaltwin.nz_providers').
"""

import logging
from typing import Optional

import geopandas as gpd
import requests

log = logging.getLogger(__name__)


def fetch_ogc_wfs_data(
        layer_id: str,
        bbox: Optional[gpd.GeoDataFrame],
        crs: int) -> gpd.GeoDataFrame:
    """
    Fetch vector data from a generic OGC WFS endpoint, matching the provider registry's
    (layer_id, bbox, crs) -> GeoDataFrame signature.

    Parameters
    ----------
    layer_id : str
        The WFS GetFeature endpoint URL for the layer, including the server base URL and 'typeNames' (or
        'typeName') query parameter, e.g. "https://example.com/geoserver/wfs?service=WFS&request=GetFeature&
        typeNames=namespace:layer". Any query parameters it already includes are preserved.
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
    RuntimeError
        If the WFS request fails or the response cannot be parsed as GeoJSON vector data.
    """
    params = {"outputFormat": "application/json", "srsName": f"EPSG:{crs}"}
    if bbox is not None:
        x_min, y_min, x_max, y_max = bbox.to_crs(crs).total_bounds
        params["bbox"] = f"{x_min},{y_min},{x_max},{y_max},EPSG:{crs}"
    try:
        log.info(f"Fetching geographic data from {layer_id} using OGC WFS.")
        response = requests.get(layer_id, params=params)
        response.raise_for_status()
        vector_data = gpd.GeoDataFrame.from_features(response.json(), crs=crs)
        log.info(f"Successfully fetched geographic data from {layer_id} using OGC WFS.")
        return vector_data
    except (requests.exceptions.RequestException, ValueError) as e:
        raise RuntimeError(f"Failed to fetch geographic data from {layer_id} using OGC WFS.") from e

#todo is this file needed?