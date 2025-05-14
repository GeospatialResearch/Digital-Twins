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

"""Functions for serving raster layers via geoserver."""

import logging
import pathlib

import requests

from src.config import EnvVariable
from src.geoserver.geoserver_common import get_geoserver_url, send_create_layer_request, upload_file_to_store, \
    style_exists

log = logging.getLogger(__name__)
_xml_header = {"Content-type": "text/xml"}


def create_layer_from_gtiff_store(geoserver_url: str, layer_name: str, workspace_name: str) -> None:
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

    Raises
    ----------
    HTTPError
        If geoserver responds with an error, raises it as an exception since it is unexpected.
    """
    with open("src/geoserver/templates/geotiff_coverage_template.xml", encoding="utf-8") as file:
        gtiff_coverage_template = file.read()
    # Fill template to get payload
    gtiff_coverage_payload = gtiff_coverage_template.format(layer_name=layer_name)
    # Send request to create layer
    send_create_layer_request(geoserver_url, layer_name, workspace_name, gtiff_coverage_payload)


def add_gtiff_to_geoserver(gtiff_filepath: pathlib.Path, workspace_name: str, model_id: int) -> None:
    """
    Upload a GeoTiff file to GeoServer, ready for serving to clients.

    Parameters
    ----------
    gtiff_filepath : pathlib.Path
        The filepath to the GeoTiff file to be served.
    workspace_name : str
        The name of the existing GeoServer workspace that the store is to be added to.
    model_id : int
        The id of the model being added, to facilitate layer naming.
    """
    gs_url = get_geoserver_url()
    layer_name = f"output_{model_id}"
    # Upload the raster into geoserver
    upload_file_to_store(gs_url, gtiff_filepath, layer_name, workspace_name)
    # We can remove the temporary raster
    gtiff_filepath.unlink()
    # Create a GIS layer from the raster file to be served from geoserver
    create_layer_from_gtiff_store(gs_url, layer_name, workspace_name)


def create_viridis_style_if_not_exists() -> None:
    """Create a GeoServer style for rasters using the viridis color scale."""
    style_name = "viridis_raster"
    log.info(f"Creating style '{style_name}.sld' if it does not exist.")
    if style_exists(style_name):
        log.debug(f"Style '{style_name}.sld' already exists.")
    else:
        # Create the style base
        create_style_data = f"""
        <style>
            <name>{style_name}</name>
            <filename>{style_name}.sld</filename>
        </style>
        """
        create_style_response = requests.post(
            f'{get_geoserver_url()}/styles',
            data=create_style_data,
            headers=_xml_header,
            auth=(EnvVariable.GEOSERVER_ADMIN_NAME, EnvVariable.GEOSERVER_ADMIN_PASSWORD)
        )
        create_style_response.raise_for_status()
    # PUT the style definition .sld file into the style base
    with open('floodresilience/flood_model/templates/viridis_raster.sld', 'rb') as payload:
        sld_response = requests.put(
            f'{get_geoserver_url()}/styles/{style_name}',
            data=payload,
            headers={"Content-type": "application/vnd.ogc.sld+xml"},
            auth=(EnvVariable.GEOSERVER_ADMIN_NAME, EnvVariable.GEOSERVER_ADMIN_PASSWORD)
        )
    sld_response.raise_for_status()
    log.info(f"Style '{style_name}.sld' created.")
