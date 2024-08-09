# -*- coding: utf-8 -*-
"""
Takes generated models and adds them to GeoServer so they can be retrieved by API calls by the frontend
or other clients.
"""  # noqa: D400

import logging
import pathlib
import shutil

import rasterio as rio
import requests

from src.config import EnvVariable
from src.geoserver.geoserver_common import get_geoserver_url, style_exists

log = logging.getLogger(__name__)
_xml_header = {"Content-type": "text/xml"}


def upload_gtiff_to_store(
        geoserver_url: str,
        gtiff_filepath: pathlib.Path,
        store_name: str,
        workspace_name: str) -> None:
    """
    Upload a GeoTiff file to a new GeoServer store, to enable serving.

    Parameters
    ----------
    geoserver_url : str
        The URL to the geoserver instance.
    gtiff_filepath : pathlib.Path
        The filepath to the GeoTiff file to be served.
    store_name : str
        The name of the new Geoserver store to be created.
    workspace_name : str
        The name of the existing GeoServer workspace that the store is to be added to.

    Raises
    ----------
    HTTPError
        If geoserver responds with an error, raises it as an exception since it is unexpected.
    """
    log.info(f"Uploading {gtiff_filepath.name} to Geoserver workspace {workspace_name}")

    # Set file copying src and dest
    geoserver_data_root = EnvVariable.DATA_DIR_GEOSERVER
    geoserver_data_dest = pathlib.Path("data") / workspace_name / gtiff_filepath.name
    # Copy file to geoserver data folder
    shutil.copyfile(gtiff_filepath, geoserver_data_root / geoserver_data_dest)
    # Send request to add data
    data = f"""
    <coverageStore>
        <name>{store_name}</name>
        <workspace>{workspace_name}</workspace>
        <enabled>true</enabled>
        <type>GeoTIFF</type>
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


def create_layer_from_store(geoserver_url: str, layer_name: str, native_crs: str, workspace_name: str) -> None:
    """
    Create a GeoServer Layer from a GeoServer store, making it ready to serve.

    Parameters
    ----------
    geoserver_url : str
        The URL to the geoserver instance.
    layer_name : str
        Defines the name of the layer in GeoServer.
    native_crs : str
        The WKT form of the CRS of the data being shown in the layer.
    workspace_name : str
        The name of the existing GeoServer workspace that the store is to be added to.

    Raises
    ----------
    HTTPError
        If geoserver responds with an error, raises it as an exception since it is unexpected.
    """
    data = f"""
    <coverage>
        <name>{layer_name}</name>
        <title>{layer_name}</title>
        <nativeCRS>{native_crs}</nativeCRS>
        <supportedFormats>
            <string>GEOTIFF</string>
            <string>TIFF</string>
            <string>PNG</string>
        </supportedFormats>
        <requestSRS><string>EPSG:2193</string></requestSRS>
        <responseSRS><string>EPSG:2193</string></responseSRS>
        <srs>EPSG:2193</srs>
    </coverage>
    """

    response = requests.post(
        f"{geoserver_url}/workspaces/{workspace_name}/coveragestores/{layer_name}/coverages",
        params={"configure": "all"},
        headers=_xml_header,
        data=data,
        auth=(EnvVariable.GEOSERVER_ADMIN_NAME, EnvVariable.GEOSERVER_ADMIN_PASSWORD)
    )
    if not response.ok:
        # Raise error manually so we can configure the text
        raise requests.HTTPError(response.text, response=response)


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
    # Retrieve CRS info from raster
    with rio.open(gtiff_filepath) as gtiff:
        gtiff_crs = gtiff.crs.wkt
    # Upload the raster into geoserver
    upload_gtiff_to_store(gs_url, gtiff_filepath, layer_name, workspace_name)
    # We can remove the temporary raster
    gtiff_filepath.unlink()
    # Create a GIS layer from the raster file to be served from geoserver
    create_layer_from_store(gs_url, layer_name, gtiff_crs, workspace_name)


def create_viridis_style_if_not_exists() -> None:
    """Create a GeoServer style for rasters using the viridis color scale."""
    style_name = "viridis_raster"
    if not style_exists(style_name):
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
    with open('src/flood_model/geoserver_templates/viridis_raster.sld', 'rb') as payload:
        sld_response = requests.put(
            f'{get_geoserver_url()}/styles/{style_name}',
            data=payload,
            headers={"Content-type": "application/vnd.ogc.sld+xml"},
            auth=(EnvVariable.GEOSERVER_ADMIN_NAME, EnvVariable.GEOSERVER_ADMIN_PASSWORD)
        )
    sld_response.raise_for_status()
