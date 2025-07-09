# -*- coding: utf-8 -*-
"""Functions for serving raster layers via geoserver."""

import logging
import pathlib
import shutil

import requests

from src.config import EnvVariable
from src.geoserver.geoserver_common import get_geoserver_url, style_exists

log = logging.getLogger(__name__)
_xml_header = {"Content-type": "text/xml"}


def upload_gtiff_to_store(
    geoserver_url: str,
    gtiff_filepath: pathlib.Path,
    store_name: str,
    workspace_name: str
) -> None:
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
    log.info(f"Uploaded {gtiff_filepath.name} to Geoserver workspace {workspace_name}.")


def create_layer_from_store(geoserver_url: str, layer_name: str, workspace_name: str) -> None:
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
    data = f"""
    <coverage>
        <name>{layer_name}</name>
        <title>{layer_name}</title>
        <nativeCRS class="projected">
            PROJCS[&quot;NZGD2000 / New Zealand Transverse Mercator 2000&quot;,
            GEOGCS[&quot;NZGD2000&quot;,
              DATUM[&quot;New Zealand Geodetic Datum 2000&quot;,
                SPHEROID[&quot;GRS 1980&quot;, 6378137.0, 298.257222101, AUTHORITY[&quot;EPSG&quot;,&quot;7019&quot;]],
                TOWGS84[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                AUTHORITY[&quot;EPSG&quot;,&quot;6167&quot;]],
              PRIMEM[&quot;Greenwich&quot;, 0.0, AUTHORITY[&quot;EPSG&quot;,&quot;8901&quot;]],
              UNIT[&quot;degree&quot;, 0.017453292519943295],
              AXIS[&quot;Geodetic longitude&quot;, EAST],
              AXIS[&quot;Geodetic latitude&quot;, NORTH],
              AUTHORITY[&quot;EPSG&quot;,&quot;4167&quot;]],
            PROJECTION[&quot;Transverse_Mercator&quot;, AUTHORITY[&quot;EPSG&quot;,&quot;9807&quot;]],
            PARAMETER[&quot;central_meridian&quot;, 173.0],
            PARAMETER[&quot;latitude_of_origin&quot;, 0.0],
            PARAMETER[&quot;scale_factor&quot;, 0.9996],
            PARAMETER[&quot;false_easting&quot;, 1600000.0],
            PARAMETER[&quot;false_northing&quot;, 10000000.0],
            UNIT[&quot;m&quot;, 1.0],
            AXIS[&quot;Easting&quot;, EAST],
            AXIS[&quot;Northing&quot;, NORTH],
            AUTHORITY[&quot;EPSG&quot;,&quot;2193&quot;]]
        </nativeCRS>
        <supportedFormats>
            <string>GEOTIFF</string>
            <string>TIFF</string>
            <string>PNG</string>
        </supportedFormats>
        <dimensions>
        <coverageDimension>
          <name>Water Depth (m)</name>
          <unit>m</unit>
          <dimensionType>
            <name>REAL_32BITS</name>
          </dimensionType>
        </coverageDimension>
        </dimensions>
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
    # Upload the raster into geoserver
    upload_gtiff_to_store(gs_url, gtiff_filepath, layer_name, workspace_name)
    # We can remove the temporary raster
    gtiff_filepath.unlink()
    # Create a GIS layer from the raster file to be served from geoserver
    create_layer_from_store(gs_url, layer_name, workspace_name)


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
