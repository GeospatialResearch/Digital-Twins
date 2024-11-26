# -*- coding: utf-8 -*-
"""Functions to handle serving database layers and views via geoserver."""

import logging
from http import HTTPStatus

import requests

from src.config import EnvVariable
from src.geoserver.geoserver_common import get_geoserver_url

log = logging.getLogger(__name__)
_xml_header = {"Content-type": "text/xml"}


def create_datastore_layer(workspace_name: str, data_store_name: str, layer_name: str, metadata_elem: str = "") -> None:
    """
    Create a GeoServer layer for a given data store if it does not currently exist.
    Can be used to create layers for a database table, or to create a database view for a custom dynamic query.

    Parameters
    ----------
    workspace_name : str
        The name of the workspace the data store is associated to
    data_store_name : str
        The name of the data store the layer is being created from.
    layer_name : str
        The name of the new layer.
        This is the same as the name of the database table if creating a layer from a table.
    metadata_elem : str = ""
        An optional XML str that contains the metadata element used to configure custom SQL queries.

    Raises
    ----------
    HTTPError
        If geoserver responds with an error, raises it as an exception since it is unexpected.

    """
    layer_full_name = f"{workspace_name}:{layer_name}"
    log.info(f"Creating datastore layer '{layer_full_name}' if it does not already exist.")
    db_exists_response = requests.get(
        f'{get_geoserver_url()}/workspaces/{workspace_name}/datastores/{data_store_name}/featuretypes.json',
        auth=(EnvVariable.GEOSERVER_ADMIN_NAME, EnvVariable.GEOSERVER_ADMIN_PASSWORD)
    )
    response_data = db_exists_response.json()
    # Parse JSON structure to get list of feature names
    top_layer_node = response_data["featureTypes"]
    # defaults to empty list if no layers exist
    layers = top_layer_node["featureType"] if top_layer_node else []
    layer_names = [layer["name"] for layer in layers]
    if layer_name in layer_names:
        # If the layer already exists, we don't have to add it again, and can instead return
        log.debug(f"Datastore layer '{layer_full_name}' already exists.")
        return
    # Construct new layer request
    data = f"""
        <featureType>
            <name>{layer_name}</name>
            <title>{layer_name}</title>
            <srs>EPSG:2193</srs>
            <nativeBoundingBox>
                <minx>1563837.8771000002</minx>
                <maxx>5175183.3933</maxx>
                <miny>1580158.7676</miny>
                <maxy>5185241.6301</maxy>
                <crs class="projected">EPSG:2193</crs>
            </nativeBoundingBox>
            <latLonBoundingBox>
                <minx>172.55213662778482</minx>
                <maxx>172.75463365676134</maxx>
                <miny>-43.576048923299616</miny>
                <maxy>-43.48487164707726</maxy>
                <crs>EPSG:4326</crs>
            </latLonBoundingBox>
            <store>
                <class>dataStore</class>
                <name>{data_store_name}</name>
            </store>
            <numDecimals>8</numDecimals>
            {metadata_elem}
        </featureType>
        """

    response = requests.post(
        f"{get_geoserver_url()}/workspaces/{workspace_name}/datastores/{data_store_name}/featuretypes",
        params={"configure": "all"},
        headers=_xml_header,
        data=data,
        auth=(EnvVariable.GEOSERVER_ADMIN_NAME, EnvVariable.GEOSERVER_ADMIN_PASSWORD)
    )
    if response.status_code == HTTPStatus.CREATED:
        log.info(f"Created new datastore layer '{layer_full_name}'.")
    else:
        # If it does not meet the expected results then raise an error
        # Raise error manually so we can configure the text
        raise requests.HTTPError(response.text, response=response)


def create_db_store_if_not_exists(db_name: str, workspace_name: str, new_data_store_name: str) -> None:
    """
    Create PostGIS database store in a GeoServer workspace for a given database.
    If it already exists, do not do anything.

    Parameters
    ----------
    db_name : str
        The name of the connected database, to connect datastore to
    workspace_name : str
        The name of the workspace to create views for
    new_data_store_name : str
        The name of the new datastore to create

    Raises
    ----------
    HTTPError
        If geoserver responds with an error, raises it as an exception since it is unexpected.
    """
    # Create request to check if database store already exists
    data_store_full_name = f"{new_data_store_name}:{workspace_name}"
    log.info(f"Creating datastore '{data_store_full_name}' if it does not already exist.")
    db_exists_response = requests.get(
        f'{get_geoserver_url()}/workspaces/{workspace_name}/datastores',
        auth=(EnvVariable.GEOSERVER_ADMIN_NAME, EnvVariable.GEOSERVER_ADMIN_PASSWORD)
    )
    response_data = db_exists_response.json()

    # Parse JSON structure to get list of data store names
    top_data_store_node = response_data["dataStores"]
    # defaults to empty list if no data stores exist
    data_stores = top_data_store_node["dataStore"] if top_data_store_node else []
    data_store_names = [data_store["name"] for data_store in data_stores]

    if new_data_store_name in data_store_names:
        # If the data store already exists we don't have to do anything
        log.debug(f"Datastore '{data_store_full_name}' already exists.")
        return

    # Create request to create database store
    create_db_store_data = f"""
        <dataStore>
          <name>{new_data_store_name}</name>
          <connectionParameters>
            <host>{EnvVariable.POSTGRES_HOST}</host>
            <port>{EnvVariable.POSTGRES_PORT}</port>
            <database>{db_name}</database>
            <user>{EnvVariable.POSTGRES_USER}</user>
            <passwd>{EnvVariable.POSTGRES_PASSWORD}</passwd>
            <dbtype>postgis</dbtype>
          </connectionParameters>
        </dataStore>
        """
    # Send request to add datastore
    response = requests.post(
        f'{get_geoserver_url()}/workspaces/{workspace_name}/datastores',
        params={"configure": "all"},
        headers=_xml_header,
        data=create_db_store_data,
        auth=(EnvVariable.GEOSERVER_ADMIN_NAME, EnvVariable.GEOSERVER_ADMIN_PASSWORD)
    )
    if response.status_code == HTTPStatus.CREATED:
        log.info(f"Created new datastore '{data_store_full_name}'.")
    # Expected responses are CREATED if the new store is created or CONFLICT if one already exists.
    else:
        # If it does not meet the expected results then raise an error
        # Raise error manually so we can configure the text
        raise requests.HTTPError(response.text, response=response)
