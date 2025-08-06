# -*- coding: utf-8 -*-
"""Core functions for serving data and working with workspaces in geoserver."""

from enum import StrEnum
from http import HTTPStatus
import logging
import os
from urllib import parse
from xml.etree import ElementTree

import requests

from src.config import EnvVariable

log = logging.getLogger(__name__)
_xml_header = {"Content-type": "text/xml"}


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


def get_geoserver_url() -> str:
    """
    Retrieve full GeoServer URL from environment variables.

    Returns
    -------
    str
        The full GeoServer URL
    """
    return f"{EnvVariable.GEOSERVER_INTERNAL_HOST}:{EnvVariable.GEOSERVER_INTERNAL_PORT}/geoserver/rest"


def create_workspace_if_not_exists(workspace_name: str) -> None:
    """
    Create a GeoServer workspace if it does not currently exist.

    Parameters
    ----------
    workspace_name : str
        The name of the workspace to create if it does not exists.

    Raises
    ----------
    HTTPError
        If geoserver responds with an error, raises it as an exception since it is unexpected.
    """
    # Create data directory for workspace if it does not already exist
    geoserver_data_root = EnvVariable.DATA_DIR_GEOSERVER
    os.makedirs(geoserver_data_root / "data" / workspace_name, exist_ok=True)

    # Create the geoserver REST API request to create the workspace
    log.info(f"Creating geoserver workspace '{workspace_name}' if it does not already exist.")
    req_body = {
        "workspace": {
            "name": workspace_name
        }
    }
    response = requests.post(
        f"{get_geoserver_url()}/workspaces",
        json=req_body,
        auth=(EnvVariable.GEOSERVER_ADMIN_NAME, EnvVariable.GEOSERVER_ADMIN_PASSWORD)
    )
    if response.status_code == HTTPStatus.CREATED:
        log.info(f"Created new workspace '{workspace_name}'.")
    elif response.status_code == HTTPStatus.CONFLICT:
        log.debug(f"Workspace '{workspace_name}' already exists.")
    else:
        # If it does not meet the expected results then raise an error
        # Raise error manually so we can configure the text
        raise requests.HTTPError(response.text, response=response)


def style_exists(style_name: str) -> bool:
    """
    Check if a GeoServer style definition already exists for a given style_name.
    The style definition may be empty.

    Parameters
    ----------
    style_name : str
        The name of the style to check for

    Returns
    -------
    bool
        True if the style exists, although it may be empty.
        False if it does not exist.

    Raises
    -------
    HTTPError
        If geoserver responds with anything but OK or NOT_FOUND, raises it as an exception since it is unexpected.
    """
    response = requests.get(
        f'{get_geoserver_url()}/styles/{style_name}.sld',
        auth=(EnvVariable.GEOSERVER_ADMIN_NAME, EnvVariable.GEOSERVER_ADMIN_PASSWORD)
    )
    if response.status_code == HTTPStatus.OK:
        return True
    if response.status_code == HTTPStatus.NOT_FOUND:
        return False
    # If it does not meet the expected results then raise an error
    # Raise error manually, so we can configure the text
    raise requests.HTTPError(response.text, response=response)


def get_workspace_layers(workspace_url: str) -> list[str]:
    """
    Retrieve all layer names from a geoserver workspace.

    Parameters
    ----------
    workspace_url : str
        The url of the geoserver workspace being queried.

    Returns
    -------
    list[str]
        The names of each layer, not including the workspace name.

    Raises
    -------
    HTTPError
        If geoserver responds with anything but OK, raises it as an exception since it is unexpected.
    """
    get_capabilities_url = f"{workspace_url}/ows?service=WFS&version=1.1.0&request=GetCapabilities"
    response = requests.get(get_capabilities_url)

    # If it does not meet the expected results then raise an error
    if response.status_code != HTTPStatus.OK:
        # Raise error manually, so we can configure the text
        raise requests.HTTPError(response.text, response=response)

    # Parse XML content
    xml_root = ElementTree.fromstring(response.content)
    namespaces = {"wfs": "http://www.opengis.net/wfs"}
    # Find the names of each feature
    name_elements = xml_root.findall("./wfs:FeatureTypeList/wfs:FeatureType/wfs:Name", namespaces)
    # Retrieve only the layer name, without workspace name
    layer_names = []
    for elem in name_elements:
        _workspace, layer_name = elem.text.split(":")
        layer_names.append(layer_name)
    return layer_names


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
    for layer_name in get_workspace_layers(workspace_url):
        layer_url_params = {
            "service": "WFS",
            "version": "1.0.0",
            "request": "GetFeature",
            "typeName": f"{workspace_name}:{layer_name}",
            "outputFormat": "application/json",
        }
        layer_url = f"{workspace_url}/ows?{parse.urlencode(layer_url_params)}"
        catalog_item = {
            "type": "geojson",
            "name": layer_name,
            "description": "Geospatial layers fetched through the Flood Resilience Digital Twin backend.",
            "url": layer_url,
        }
        catalog_group.append(catalog_item)
    return {
        "type": "group",
        "name": workspace_name,
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
