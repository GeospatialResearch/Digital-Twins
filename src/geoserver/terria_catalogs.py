# -*- coding: utf-8 -*-
# Copyright © 2021-2025 Geospatial Research Institute Toi Hangarau
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

"""Functions for handling creating TerriaJS catalog items by reading the geoserver workspaces."""
from enum import StrEnum

from .database_layers import get_workspace_vector_layers
from .raster_layers import get_workspace_raster_layers
from src.config import EnvVariable


class Workspaces(StrEnum):
    """
    Enum to label and access geoserver workspaces initialized within data_to_db.py.

    Attributes
    ----------
    STATIC_FILES_WORKSPACE : str
        Workspace containing layers loaded from static files.
    INPUT_LAYERS_WORKSPACE : str
        Workspace containing layers loaded from external sources used as input for later modelling or visualisation.
    """

    STATIC_FILES_WORKSPACE = "static_files"
    INPUT_LAYERS_WORKSPACE = "input_layers"
    EXTRUDED_LAYERS_WORKSPACE = "extruded_layers"


def create_vector_layer_catalog_item(
    workspace_name: str,
    workspace_url: str,
    layer_name: str,
    max_features: int = 60000
) -> dict:
    """
    Create a JSON TerriaJS catalog item for a single GeoServer vector WFS layer.

    Parameters
    ----------
    workspace_name : str

    workspace_url : str
        The URL to the GeoServer workspace.
    layer_name : str
        The name of the layer in Geoserver.
    max_features : int = 60000
        The maximum number of features to fetch from Geoserver.

    Returns
    -------
    dict
        JSON TerriaJS catalog item for a single GeoServer raster WMS layer.
    """
    catalog_item = {
        "type": "wfs",
        "name": layer_name,
        "description": "Geospatial layers fetched through the Flood Resilience Digital Twin backend.",
        "url": f"{workspace_url}/ows",
        "typeNames": f"{workspace_name}:{layer_name}",
        "maxFeatures": max_features,
    }
    if workspace_name == Workspaces.EXTRUDED_LAYERS_WORKSPACE:
        catalog_item["heightProperty"] = "Ext_height"
    return catalog_item


def create_raster_layer_catalog_item(workspace_url: str, layer_name: str) -> dict:
    """
    Create a JSON TerriaJS catalog item for a single GeoServer raster WMS layer.

    Parameters
    ----------
    workspace_url : str
        The URL to the GeoServer workspace.
    layer_name : str
        The name of the layer in Geoserver.

    Returns
    -------
    dict
        JSON TerriaJS catalog item for a single GeoServer raster WMS layer.
    """
    catalog_item = {
        "type": "wms",
        "name": layer_name,
        "url": f"{workspace_url}/wms",
        "layers": layer_name,
        "styles": layer_name,
    }
    return catalog_item


def get_layers_as_terria_group(workspace_name: str) -> dict:
    """
    Query geoserver for available layers within a workspace, and return a terria catalog to serve the data.
    The style definition may be empty.

    Parameters
    ----------
    workspace_name : str
        The name of the geoserver workspace to query for.

    Returns
    -------
    dict
        Represents the Terria JSON catalog group items for each layer within the workspace.

    Raises
    -------
    HTTPError
        If geoserver responds with anything but OK or NOT_FOUND, raises it as an exception since it is unexpected.
    """
    catalog_group = []
    workspace_url = f"{EnvVariable.GEOSERVER_HOST}:{EnvVariable.GEOSERVER_PORT}/geoserver/{workspace_name}"
    for vector_layer in get_workspace_vector_layers(workspace_name):
        catalog_item = create_vector_layer_catalog_item(workspace_name, workspace_url, vector_layer)
        catalog_group.append(catalog_item)
    for raster_layer in get_workspace_raster_layers(workspace_name):
        catalog_item = create_raster_layer_catalog_item(workspace_url, raster_layer)
        catalog_group.append(catalog_item)
    return {
        "type": "group",
        "name": workspace_name.replace("_", " ").title(),
        "members": catalog_group,
        "isOpen": True,
    }


def get_terria_catalog() -> dict:
    """
    Query geoserver for available layers from key workspaces, and return a terria catalog to serve the data.

    Returns
    -------
    dict
        Represents the Terria JSON catalog items for each layer within the workspaces.

    Raises
    -------
    HTTPError
        If geoserver responds with anything but OK or NOT_FOUND, raises it as an exception since it is unexpected.
    """
    return {"catalog": [get_layers_as_terria_group(workspace) for workspace in Workspaces]}
