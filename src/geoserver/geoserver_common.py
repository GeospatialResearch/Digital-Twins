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

"""Core functions for serving data and working with workspaces in geoserver."""

import logging
from http import HTTPStatus
import os
import shutil

import pathlib
import requests

from src.config import EnvVariable

log = logging.getLogger(__name__)
_xml_header = {"Content-type": "text/xml"}


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


def upload_file_to_store(
    geoserver_url: str,
    file_to_add: pathlib.Path,
    store_name: str,
    workspace_name: str
) -> None:
    """
    Upload a file to a new GeoServer store, to enable serving.

    Parameters
    ----------
    geoserver_url : str
        The URL to the geoserver instance.
    file_to_add : pathlib.Path
        The filepath to the GeoTiff file to be served, currently support NetCDF and GeoTiff.
    store_name : str
        The name of the new Geoserver store to be created.
    workspace_name : str
        The name of the existing GeoServer workspace that the store is to be added to.

    Raises
    ----------
    HTTPError
        If geoserver responds with an error, raises it as an exception since it is unexpected.
    ValueError
        If file_to_add does not have a file extension matching one of the supported file types..

    """
    log.info(f"Uploading {file_to_add.name} to Geoserver workspace {workspace_name}")
    # Create map of file extensions to their geoserver type parameter
    file_extension_to_types = {
        ".tiff": "GeoTIFF",
        ".tif": "GeoTIFF",
        ".nc": "NetCDF",
    }
    # Check file extension validity
    file_extension = file_to_add.suffix
    if file_extension not in file_extension_to_types:
        raise ValueError(f"Unsupported file extension {file_extension} not in {file_extension_to_types.keys()}")

    # Set file copying src and dest
    geoserver_data_root = EnvVariable.DATA_DIR_GEOSERVER
    geoserver_data_dest = pathlib.Path("data") / workspace_name / file_to_add.name
    # Copy file to geoserver data folder
    shutil.copyfile(file_to_add, geoserver_data_root / geoserver_data_dest)
    # Send request to add data
    data = f"""
        <coverageStore>
            <name>{store_name}</name>
            <workspace>{workspace_name}</workspace>
            <enabled>true</enabled>
            <type>{file_extension_to_types[file_extension]}</type>
            <url>file:{geoserver_data_dest.as_posix()}</url>
        </coverageStore>
        """
    response = requests.post(
        f'{geoserver_url}/workspaces/{workspace_name}/coveragestores',
        params={"configure": "all"},
        headers=_xml_header,
        data=data,
        auth=(EnvVariable.GEOSERVER_ADMIN_NAME, EnvVariable.GEOSERVER_ADMIN_PASSWORD),
    )
    if not response.ok:
        # Raise error manually so we can configure the text
        raise requests.HTTPError(response.text, response=response)
    log.info(f"Uploaded {file_to_add.name} to Geoserver workspace {workspace_name}.")


def send_create_layer_request(geoserver_url: str, layer_name: str, workspace_name: str, coverage_payload: str) -> None:
    """
    Create a GeoServer Layer from a GeoServer store, making it ready to serve.

    Parameters
    ----------
    geoserver_url : str
        The URL to the geoserver instance.
    layer_name : str
        Defines the name of the layer in GeoServer.
    workspace_name : str
        The name of the existing GeoServer workspace that the store is to be added to.
    coverage_payload : str
        The coverage XML data to send in the Geoserver request payload.

    Raises
    ----------
    HTTPError
        If geoserver responds with an error, raises it as an exception since it is unexpected.
    """
    # Send request to create layer
    response = requests.post(
        f"{geoserver_url}/workspaces/{workspace_name}/coveragestores/{layer_name}/coverages",
        params={"configure": "all"},
        headers=_xml_header,
        data=coverage_payload,
        auth=(EnvVariable.GEOSERVER_ADMIN_NAME, EnvVariable.GEOSERVER_ADMIN_PASSWORD)
    )
    if not response.ok:
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
