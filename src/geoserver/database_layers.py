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

"""Functions to handle serving database layers and views via geoserver."""

import logging
from http import HTTPStatus

import geopandas as gpd
import requests

from src.config import EnvVariable
from src.digitaltwin.data_to_db import check_table_exists
from src.digitaltwin.setup_environment import get_database
from src.geoserver.geoserver_common import create_workspace_if_not_exists, get_geoserver_url

log = logging.getLogger(__name__)
_xml_header = {"Content-type": "text/xml"}

MAIN_DB_STORE_NAME = f"{EnvVariable.POSTGRES_DB} PostGIS"


def get_workspace_vector_layers(workspace_name: str, data_store_name: str = MAIN_DB_STORE_NAME) -> list[str]:
    """
    Retrieve all vector layer names from a geoserver workspace.

    Parameters
    ----------
    workspace_name : str
        The name of the geoserver workspace being queried.
    data_store_name : str = src.geoserver.database_layers.MAIN_DB_STORE_NAME
        The name of the geoserver data store to query.

    Returns
    -------
    list[str]
        The names of each layer, not including the workspace name.

    Raises
    -------
    HTTPError
        If geoserver responds with anything but OK, raises it as an exception since it is unexpected.
    """
    vector_layers_response = requests.get(
        f'{get_geoserver_url()}/workspaces/{workspace_name}/datastores/{data_store_name}/featuretypes.json',
        auth=(EnvVariable.GEOSERVER_ADMIN_NAME, EnvVariable.GEOSERVER_ADMIN_PASSWORD)
    )
    vector_layers_response.raise_for_status()
    response_data = vector_layers_response.json()
    # Parse JSON structure to get list of feature names
    top_layer_node = response_data["featureTypes"]
    # defaults to empty list if no layers exist
    layers = top_layer_node["featureType"] if top_layer_node else []
    layer_names = [layer["name"] for layer in layers]
    return layer_names


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

    if layer_name in get_workspace_vector_layers(workspace_name):
        # If the layer already exists, we don't have to add it again, and can instead return
        log.debug(f"Datastore layer '{layer_full_name}' already exists.")
        return
    # Find SRS/CRS information
    engine = get_database()
    if check_table_exists(engine, layer_name):
        gdf = gpd.read_postgis(f'SELECT * FROM "{layer_name}"', engine, "geometry")
    else:
        # Default values if nothing else is available
        gdf = gpd.read_file("selected_polygon.geojson")
    minx, miny, maxx, maxy = gdf.total_bounds
    minx4326, miny4326, maxx4326, maxy4326 = gdf.to_crs(4326).total_bounds
    crs = gdf.crs.to_epsg()
    # Construct new layer request
    data = f"""
        <featureType>
            <name>{layer_name}</name>
            <title>{layer_name}</title>
            <srs>EPSG:{crs}</srs>
            <nativeBoundingBox>
                <minx>{minx}</minx>
                <maxx>{maxx}</maxx>
                <miny>{miny}</miny>
                <maxy>{maxy}</maxy>
                <crs class="projected">EPSG:{crs}</crs>
            </nativeBoundingBox>
            <latLonBoundingBox>
                <minx>{minx4326}</minx>
                <maxx>{maxx4326}</maxx>
                <miny>{miny4326}</miny>
                <maxy>{maxy4326}</maxy>
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
            <host>{EnvVariable.POSTGRES_INTERNAL_HOST}</host>
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


def create_main_db_store(workspace_name: str) -> str:
    """
    Create PostGIS database store in a GeoServer workspace for the main PostGIS database.
    If it already exists, do not do anything.

    Parameters
    ----------
    workspace_name : str
       The name of the workspace to create views for

    Returns
    -------
    str
        The name of the new datastore created.

    Raises
    ----------
    HTTPError
       If geoserver responds with an error, raises it as an exception since it is unexpected.
    """
    log.debug(f"Creating {MAIN_DB_STORE_NAME} store if it does not exist")
    # Create workspace if it doesn't exist, so that the namespaces can be separated if multiple dbs are running
    create_workspace_if_not_exists(workspace_name)
    # Create a new database store if geoserver is not yet configured for that database
    db_name = EnvVariable.POSTGRES_DB
    create_db_store_if_not_exists(db_name, workspace_name, MAIN_DB_STORE_NAME)
    return MAIN_DB_STORE_NAME
