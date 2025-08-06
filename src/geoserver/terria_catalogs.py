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
from urllib.parse import urlencode

from .database_layers import get_workspace_layers
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


def get_layers_as_terria_group(workspace_name: str, max_features: int = 30000) -> dict:
    """
    Query geoserver for available layers within a workspace, and return a terria catalog to serve the data.
    The style definition may be empty.

    Parameters
    ----------
    workspace_name : str
        The name of the geoserver workspace to query for.
    max_features : int = 30000
        The maximum number of features to serve for each layer.

    Returns
    -------
    dict
        Represents the Terria JSON catalog group items for each layer within the workspace.

    Raises
    -------
    HTTPError
        If geoserver responds with anything but OK or NOT_FOUND, raises it as an exception since it is unexpected.
    """

    workspace_url = f"{EnvVariable.GEOSERVER_INTERNAL_HOST}:{EnvVariable.GEOSERVER_INTERNAL_PORT}/geoserver/{workspace_name}"

    catalog_group = []
    for layer_name in get_workspace_layers(workspace_name):
        layer_url_params = {
            "service": "WFS",
            "version": "1.0.0",
            "request": "GetFeature",
            "typeName": f"{workspace_name}:{layer_name}",
            "outputFormat": "application/json",
        }
        layer_url = f"{workspace_url}/ows?{urlencode(layer_url_params)}"
        catalog_item = {
            "type": "geojson",
            "name": layer_name,
            "description": "Geospatial layers fetched through the Flood Resilience Digital Twin backend.",
            "url": layer_url,
        }
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
