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

"""Core functions for serving data and working with workspaces in geoserver."""

from http import HTTPStatus
import logging
import os

import requests

from eddie.config import EnvVariable

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


def get_workspace_url(workspace_name: str) -> str:
    """
    Format the URL for a GeoServer workspace from its name.
    Simple helper function.

    Parameters
    ----------
    workspace_name : str
        The name of the workspace the data store resides in.

    Returns
    -------
    str
        A formatted URL for the base-endpoint of the workspace.
    """
    return f"{get_geoserver_url()}/workspaces/{workspace_name}"


def get_data_store_url(workspace_name: str, data_store_name: str) -> str:
    """
    Format the URL for a GeoServer data store from its parameters.
    Simple helper function.

    Parameters
    ----------
    workspace_name : str
        The name of the workspace the data store resides in.
    data_store_name : str
        The name of the data store.

    Returns
    -------
    str
        A formatted URL for the base-endpoint of the data store.
    """
    return f"{get_workspace_url(workspace_name)}/datastores/{data_store_name}"


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


def restrict_wps_service() -> None:
    """
    Restrict the GeoServer WPS Execute operation to administrators.

    SLD rendering transformations used by WMS styles are unaffected, because they do not go through the WPS service.
    Safe to repeat: GeoServer refuses to add a rule that already exists, so the rule is then overwritten instead.

    Raises
    ----------
    HTTPError
        If geoserver responds with an error, raises it as an exception since it is unexpected.
    """
    acl_url = f"{get_geoserver_url()}/security/acl/services"
    auth = (EnvVariable.GEOSERVER_ADMIN_NAME, EnvVariable.GEOSERVER_ADMIN_PASSWORD)
    rule = {"wps.Execute": "ROLE_ADMINISTRATOR"}
    response = requests.post(acl_url, json=rule, auth=auth)
    if response.status_code == HTTPStatus.CONFLICT:
        # The rule already exists, possibly with another role
        response = requests.put(acl_url, json=rule, auth=auth)
    if not response.ok:
        # Raise error manually so we can configure the text
        raise requests.HTTPError(response.text, response=response)
    log.info("Restricted GeoServer WPS Execute to administrators.")


def does_resource_exist(resource_url: str) -> bool:
    """
    Check whether a GeoServer resource (e.g. a workspace, store, or layer) exists at the given REST URL.

    Sends an authenticated GET request to the resource URL and interprets the response status code:
    a 200 OK means the resource exists, a 404 Not Found means it does not, and any other status is
    treated as an unexpected error.

    Parameters
    ----------
    resource_url : str
        The full GeoServer REST API URL of the resource to check, e.g.
        "{geoserver_url}/workspaces/{workspace_name}".

    Returns
    ----------
    bool
        True if the resource exists (GeoServer returns 200 OK), False if it does not exist
        (GeoServer returns 404 Not Found).

    Raises
    ----------
    HTTPError
        If geoserver responds with any status code other than 200 or 404, raises it as an exception
        since it is unexpected.
    """
    resource_exists_response = requests.get(
        resource_url,
        auth=(EnvVariable.GEOSERVER_ADMIN_NAME, EnvVariable.GEOSERVER_ADMIN_PASSWORD)
    )
    match resource_exists_response.status_code:
        case HTTPStatus.OK:
            return True
        case HTTPStatus.NOT_FOUND:
            return False
        case _:
            # Raise error manually so we can configure the text
            raise requests.HTTPError(resource_exists_response.text, response=resource_exists_response)
