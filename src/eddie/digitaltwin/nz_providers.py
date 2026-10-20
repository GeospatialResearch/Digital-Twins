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
Optional New Zealand data providers (StatsNZ, LINZ, MFE), built on the 'geoapis' library, plus the NZ-specific
'get_nz_boundary' helper. This module is deliberately kept out of core: it demonstrates that the generic provider
registry design (see 'provider_registry.py') lets country/organisation-specific providers live entirely outside
core, needing no core code changes to add or remove.

This module requires NZ-specific API keys (see 'eddie.config.EnvVariable') to function, which is what makes it
optional rather than core; 'geoapis' itself is already a core dependency, used by the generic 'ogc_wfs' provider
(see 'get_data_using_geoapis.py'), whose 'WfsQueryBase' subclasses and helpers this module reuses.

Importing this module has the side effect of registering the "StatsNZ", "LINZ" and "MFE" providers into the
core provider registry; it is never imported by core code, so it has no effect unless an application explicitly
opts in with `import eddie.digitaltwin.nz_providers`.
"""

import logging
from typing import Callable

from geoapis.vector import Linz, StatsNz, WfsQueryBase
import geopandas as gpd
from sqlalchemy.engine import Connection

from eddie import config
from eddie.digitaltwin.get_data_using_geoapis import fetch_vector_data_using_geoapis, resolve_wfs_fetch_crs
from eddie.digitaltwin.provider_registry import register_provider

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


# The required API key env var for each NZ-specific data provider. The 'geoapis' fetcher *class* is deliberately
# NOT captured here (e.g. as a dict of (class, key) tuples): that dict would be built once at module import time,
# permanently binding the then-current 'StatsNz'/'Linz'/'MFE' objects into the closure below, so tests patching
# 'nz_providers.StatsNz' etc. afterwards would never be seen by already-registered providers. Instead, each
# fetcher class is looked up by its module-global name afresh inside 'provider()' on every call.
_NZ_PROVIDER_KEYS = {
    "StatsNZ": config.EnvVariable.STATSNZ_API_KEY,
    "LINZ": config.EnvVariable.LINZ_API_KEY,
    "MFE": config.EnvVariable.MFE_API_KEY,
}


def _make_nz_provider(data_provider: str) -> Callable[[str, gpd.GeoDataFrame | None, int], gpd.GeoDataFrame]:
    """
    Build a provider registry callable, matching the (layer_id, bbox, crs) -> GeoDataFrame signature, for a single
    NZ-specific 'geoapis'-backed data provider.

    Parameters
    ----------
    data_provider : str
        The NZ data provider name to bind the callable to. Supported values: "StatsNZ", "LINZ", "MFE".

    Returns
    -------
    Callable[[str, gpd.GeoDataFrame | None, int], gpd.GeoDataFrame]
        A provider callable for use with 'provider_registry.register_provider'.

    Raises
    ------
    ValueError
        If an unsupported 'data_provider' value is given.
    """
    if data_provider not in _NZ_PROVIDER_KEYS:
        raise ValueError(f"Unsupported NZ data_provider: '{data_provider}'")
    api_key = _NZ_PROVIDER_KEYS[data_provider]

    def provider(layer_id: str, bbox: gpd.GeoDataFrame | None, crs: int) -> gpd.GeoDataFrame:
        """
        Fetch a layer from this NZ data provider using geoapis, matching the provider registry signature.

        Parameters
        ----------
        layer_id : str
            The numeric geoapis layer ID, as a string.
        bbox : gpd.GeoDataFrame | None
            The bounding area to query within, in any CRS. If None, no bounding polygon is applied and the
            fetch covers all of New Zealand (used for 'full' fetch_mode layers).
        crs : int
            The EPSG code the returned GeoDataFrame should be reprojected to.

        Returns
        -------
        gpd.GeoDataFrame
            The fetched, cleaned vector data, reprojected to the requested CRS.
        """
        # Resolved by name (not captured above) against this module's current globals on every call, so that
        # tests can mock.patch.object(nz_providers, "StatsNz") etc. and have it take effect.
        fetcher_class = {"StatsNZ": StatsNz, "LINZ": Linz, "MFE": MFE}[data_provider]
        # Default bounding_polygon of None covers all of New Zealand (used for 'full' fetch_mode layers)
        fetch_crs = resolve_wfs_fetch_crs(crs)
        bounding_polygon = bbox.to_crs(fetch_crs) if bbox is not None else None
        fetcher = fetcher_class(key=api_key, crs=fetch_crs, bounding_polygon=bounding_polygon, verbose=False)
        return fetch_vector_data_using_geoapis(fetcher, int(layer_id), crs)

    return provider


def get_nz_boundary(conn: Connection, to_crs: int) -> gpd.GeoDataFrame:
    """
    Get the boundary of New Zealand in the specified Coordinate Reference System (CRS).

    Parameters
    ----------
    conn : Connection
        The connection used to connect to the database.
    to_crs : int
        Coordinate Reference System (CRS) code to which the boundary will be converted.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame representing the boundary of New Zealand in the specified CRS.
    """
    # Query the 'region_geometry' table from the database
    query = "SELECT * FROM region_geometry;"
    region_geometry = gpd.GeoDataFrame.from_postgis(query, conn, geom_col="geometry")
    # Dissolve and explode the geometries to get the boundary of New Zealand
    nz_boundary = region_geometry.dissolve(aggfunc="sum").explode(index_parts=True).reset_index(level=0, drop=True)
    # Calculate the area of each geometry and sort them in descending order
    nz_boundary["geometry_area"] = nz_boundary["geometry"].area
    nz_boundary = nz_boundary.sort_values(by="geometry_area", ascending=False).head(1)
    # Convert to the desired coordinate reference system (CRS)
    nz_boundary = nz_boundary.to_crs(to_crs)
    return nz_boundary


# Register the NZ providers under the same 'data_provider' names already used in existing instructions
# files/databases, so no instructions data needs to change when this module is adopted.
register_provider("StatsNZ", _make_nz_provider("StatsNZ"))
register_provider("LINZ", _make_nz_provider("LINZ"))
register_provider("MFE", _make_nz_provider("MFE"))
