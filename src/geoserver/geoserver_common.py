# -*- coding: utf-8 -*-
"""Core functions for serving data and working with workspaces in geoserver."""

import logging
import os
from http import HTTPStatus

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
    return f"{EnvVariable.GEOSERVER_HOST}:{EnvVariable.GEOSERVER_PORT}/geoserver/rest"


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
    log.info(f"Creating geoserver workspace {workspace_name} if it does not already exist.")
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
