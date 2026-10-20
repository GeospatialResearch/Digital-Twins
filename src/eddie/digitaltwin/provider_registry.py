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
A small, name-based registry of data providers used to fetch geospatial data for 'geospatial_layers' records.
Each provider is a callable of the form (layer_id, bbox, crs) -> GeoDataFrame. Core ships only the generic
providers ('ogc_wfs' and 'arcgis_rest'), which work against any standards-compliant OGC WFS / ArcGIS REST
service and require no provider-specific account or API key (the generic 'ogc_wfs' provider is itself built on
the 'geoapis' library's 'WfsQuery' class - see 'get_data_using_geoapis.py'). Provider-specific extras (e.g. the
optional 'eddie.digitaltwin.nz_providers' module, which adds the StatsNZ/LINZ/MFE
'geoapis' based providers) register themselves into this same registry on import, without requiring any change
to this file or to core fetch code - this is the generic design the registry enables.
"""

import logging
from typing import Callable, Dict, List, Optional

import geopandas as gpd

log = logging.getLogger(__name__)

# A provider fetches data for a single layer: given the provider-specific layer identifier (e.g. a numeric ID for
# geoapis-based providers, or a full feature layer / WFS GetFeature URL for the generic providers), an optional
# bounding GeoDataFrame to restrict the request to (None meaning "fetch everything"), and the desired output CRS.
ProviderFunc = Callable[[str, Optional[gpd.GeoDataFrame], int], gpd.GeoDataFrame]

_PROVIDERS: Dict[str, ProviderFunc] = {}


def register_provider(name: str, provider: ProviderFunc, overwrite: bool = False) -> None:
    """
    Register a data provider callable under the given name, so it can be looked up by 'get_provider'.

    Parameters
    ----------
    name : str
        The provider name, matching the 'data_provider' field used in instructions records.
    provider : ProviderFunc
        A callable of the form (layer_id, bbox, crs) -> GeoDataFrame.
    overwrite : bool = False
        Whether to allow replacing an already-registered provider of the same name. Default is False.

    Raises
    ------
    ValueError
        If a provider is already registered under 'name' and 'overwrite' is False.
    """
    if not overwrite and name in _PROVIDERS:
        raise ValueError(f"A provider is already registered under the name '{name}'.")
    log.debug(f"Registering data provider '{name}'.")
    _PROVIDERS[name] = provider


def get_provider(name: str) -> ProviderFunc:
    """
    Look up a registered data provider by name.

    Parameters
    ----------
    name : str
        The provider name, matching the 'data_provider' field used in instructions records.

    Returns
    -------
    ProviderFunc
        The callable registered under 'name', of the form (layer_id, bbox, crs) -> GeoDataFrame.

    Raises
    ------
    KeyError
        If no provider is registered under 'name'. NZ-specific providers (StatsNZ, LINZ, MFE) require the optional
        'nz_providers' module to be imported before they are available here.
    """
    try:
        return _PROVIDERS[name]
    except KeyError:
        raise KeyError(
            f"Unknown data provider '{name}'. Registered providers: {sorted(_PROVIDERS)}. "
            "Provider-specific extras (e.g. for StatsNZ/LINZ/MFE, via "
            "'eddie.digitaltwin.nz_providers') must be installed and imported before their providers are "
            "available."
        ) from None


def registered_providers() -> List[str]:
    """
    List the names of all currently registered data providers.

    Returns
    -------
    List[str]
        The sorted list of registered provider names.
    """
    return sorted(_PROVIDERS)


# Register the generic core providers. Import is deferred to the bottom of the module to avoid a circular
# import, since these modules do not depend on this registry module themselves.
from eddie.digitaltwin.arcgis_rest_api import (  # noqa: E402  pylint: disable=wrong-import-position
    fetch_arcgis_rest_data)
from eddie.digitaltwin.get_data_using_geoapis import (  # noqa: E402  pylint: disable=wrong-import-position
    fetch_generic_wfs_data)

register_provider("arcgis_rest", fetch_arcgis_rest_data)
register_provider("ogc_wfs", fetch_generic_wfs_data)
