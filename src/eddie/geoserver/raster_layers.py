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

"""Functions for serving raster layers via geoserver."""

from http import HTTPStatus
from importlib import resources
import logging
import pathlib
from typing import NamedTuple

import rasterio as rio
from rasterio import warp
import requests

from eddie.config import EnvVariable
from eddie.geoserver.geoserver_common import get_geoserver_url

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
    # Copy file to geoserver data folder, reprojected to web mercator for speedy visualisation
    reproject_raster_to_web_mercator(gtiff_filepath, geoserver_data_root / geoserver_data_dest)
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


def reproject_raster_to_web_mercator(src_path: pathlib.Path, dst_path: pathlib.Path) -> None:
    """
    Create a copy of the raster at the dst_path with the data reprojected to web mercator.
    This allows for faster serving when web front-ends request data from GeoServer, by preprocessing the reprojection.

    Parameters
    ----------
    src_path : pathlib.Path
        The path to the source raster.
    dst_path : pathlib.Path
        The path to the new reprojected raster to be created.
    """
    web_mercator_epsg = 3857
    dst_crs = rio.crs.CRS.from_epsg(web_mercator_epsg)
    with rio.open(src_path, 'r') as src:
        # Calculate the destination transform, width, and height
        transform, width, height = warp.calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds
        )

        # Copy the source metadata and update it for the destination
        dst_meta = src.profile.copy()
        dst_meta.update({
            'crs': dst_crs,
            'transform': transform,
            'width': width,
            'height': height,
            'driver': 'GTiff',  # Ensure output format is GeoTIFF or other compatible format
            'nodata': src.nodata  # Set the NoData value for the output
        })

        # Open the destination file in 'write' mode and perform the reprojection
        with rio.open(dst_path, 'w', **dst_meta) as dst:
            for i in range(1, src.count + 1):
                warp.reproject(
                    source=rio.band(src, i),
                    destination=rio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=dst.transform,
                    dst_crs=dst.crs,
                    resampling=warp.Resampling.nearest
                )


class CoverageDimension(NamedTuple):
    """
    Represents the dimensions of a raster layer.

    Attributes
    ----------
    band_name : str
        The name of this dimension's band, e.g. 'elevation_above_sea_level'.
    unit : str
        The unit this dimension is measure in, e.g. 'm'.
    dimension_type : str
        The type of this dimension's data e.g. 'REAL_32BITS'.
    """

    band_name: str
    unit: str
    dimension_type: str


def create_layer_from_gtiff_store(
    geoserver_url: str,
    layer_name: str,
    workspace_name: str,
    coverage_dimensions: list[CoverageDimension]
) -> None:
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
    coverage_dimensions : list[CoverageDimension]
        Information about the bands in the GeoTiff file to be served.

    Raises
    ----------
    HTTPError
        If geoserver responds with an error, raises it as an exception since it is unexpected.
    """
    # Read the template xml file in a way that works for downstream users of the eddie library.
    gtiff_coverage_template = resources.read_text("eddie.geoserver.templates", "geotiff_coverage_template.xml")
    coverage_dimensions_xml = format_coverage_dimensions(coverage_dimensions)
    # Fill template to get payload
    gtiff_coverage_payload = gtiff_coverage_template.format(layer_name=layer_name,
                                                            coverage_dimensions_xml=coverage_dimensions_xml)
    # Send request to create layer
    send_create_layer_request(geoserver_url, layer_name, workspace_name, gtiff_coverage_payload)


def format_coverage_dimensions(coverage_dimensions: list[CoverageDimension]) -> str:
    """
    Format a list of coverage dimensions into an XML string ready to be used in a GeoServer payload.

    Parameters
    ----------
    coverage_dimensions : list[CoverageDimension]
        Information about the bands in the GeoTiff file to be served.

    Returns
    -------
    str
        XML formatted str containing one or more <coverageDimension> elements.

    Raises
    ------
    ValueError
        If the `coverage_dimensions` list is empty.
    """
    # Cannot accept no coverage dimensions
    if len(coverage_dimensions) == 0:
        raise ValueError("No coverage dimensions provided")

    # Read the template xml file in a way that works for downstream users of the eddie library.
    coverage_dimension_template = resources.read_text("eddie.geoserver.templates",
                                                      "geotiff_coverage_dimension_template.xml")
    filled_dimensions = []
    for band_name, unit, dimension_type in coverage_dimensions:
        # Format each <coverageDimension> element str and add them to a list
        filled_dimension = coverage_dimension_template.format(
            band_name=band_name, unit=unit, dimension_type=dimension_type)
        filled_dimensions.append(filled_dimension)
    # Join each of the <coverageDimension> elements into one xml str
    coverage_dimensions_xml = "".join(dim for dim in filled_dimensions)
    return coverage_dimensions_xml


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


def add_gtiff_to_geoserver(
    gtiff_filepath: pathlib.Path,
    workspace_name: str,
    layer_name: str,
    coverage_dimensions: list[CoverageDimension] | None = None
) -> None:
    """
    Upload a GeoTiff file to GeoServer, ready for serving to clients.

    Parameters
    ----------
    gtiff_filepath : pathlib.Path
        The filepath to the GeoTiff file to be served.
    workspace_name : str
        The name of the existing GeoServer workspace that the store is to be added to.
    layer_name : str
        The name of the layer being added must be unique within the workspace. #todo check uniqueness
    coverage_dimensions : list[CoverageDimension] | None
        Information about the bands in the GeoTiff file to be served. If no information is provided, it is assumed that
        the raster is single band and its units are 'm'
    """
    gs_url = get_geoserver_url()
    if layer_name in get_workspace_raster_layers(workspace_name):
        log.info(f"Replacing raster layer {workspace_name}:{layer_name} because it already exists.")
        delete_store(layer_name, workspace_name)
    # Upload the raster into geoserver
    upload_gtiff_to_store(gs_url, gtiff_filepath, layer_name, workspace_name)
    # Ensure the coverage_dimensions exist
    if coverage_dimensions is None or len(coverage_dimensions) == 0:
        # If they don't exist, assume that the raster is single band and its units are 'm'
        coverage_dimensions = [CoverageDimension(layer_name, "m", "REAL_32BITS")]
        # Create a GIS layer from the raster file to be served from geoserver
    create_layer_from_gtiff_store(gs_url, layer_name, workspace_name, coverage_dimensions)


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


def delete_style(style_name: str) -> None:
    """
    Delete a style from the default geoserver workspace

    Parameters
    ----------
    style_name : str
        The name of the style being deleted.
    """
    delete_style_response = requests.delete(
        f'{get_geoserver_url()}/styles/{style_name}',
        auth=(EnvVariable.GEOSERVER_ADMIN_NAME, EnvVariable.GEOSERVER_ADMIN_PASSWORD)
    )
    delete_style_response.raise_for_status()


def add_style(style_file: pathlib.Path, replace: bool = False) -> None:
    """
    Create a GeoServer style in the default workspace for rasters using a SLD style definition file.

    Parameters
    ----------
    style_file : pathlib.Path
        The path to the style definition (SLD) file to upload.
    replace : bool = False
        True if you want to replace the existing style, False to skip adding the style if one already exists.
    """
    style_name = style_file.stem
    log.info(f"Creating style '{style_file.name}' if it does not exist.")
    style_currently_exists = style_exists(style_name)
    if style_currently_exists:
        log.debug(f"Style '{style_name}.sld' already exists.")
        if replace:
            log.debug(f"Deleting '{style_name}.sld'.")
            delete_style(style_name)
            style_currently_exists = False
    if not style_currently_exists:  # Check again instead of using else because it may have been deleted
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
    with open(style_file, 'rb') as payload:
        sld_response = requests.put(
            f'{get_geoserver_url()}/styles/{style_name}',
            data=payload,
            headers={"Content-type": "application/vnd.ogc.sld+xml"},
            auth=(EnvVariable.GEOSERVER_ADMIN_NAME, EnvVariable.GEOSERVER_ADMIN_PASSWORD)
        )
    sld_response.raise_for_status()
    log.info(f"Style '{style_name}.sld' created.")


def delete_store(store_name: str, workspace_name: str) -> None:
    """
    Delete a Geoserver CoverageStore from a workspace.

    Parameters
    ----------
    store_name : str
        The name of the Geoserver CoverageStore to delete.
    workspace_name : str
        The name of the workspace to delete the store from.

    Raises
    ------
    HTTPError
        If geoserver responds with an error status code.
    """
    delete_store_request = requests.delete(
        f'{get_geoserver_url()}/workspaces/{workspace_name}/coveragestores/{store_name}',
        auth=(EnvVariable.GEOSERVER_ADMIN_NAME, EnvVariable.GEOSERVER_ADMIN_PASSWORD),
        params={"purge": "all", "recurse": True}
    )
    delete_store_request.raise_for_status()


def get_workspace_raster_layers(workspace_name: str) -> list[str]:
    """
    Retrieve all raster layer names from a geoserver workspace.

    Parameters
    ----------
    workspace_name : str
        The name of the geoserver workspace being queried.

    Returns
    -------
    list[str]
        The names of each layer, not including the workspace name.

    Raises
    -------
    HTTPError
        If geoserver responds with anything but OK, raises it as an exception since it is unexpected.
    """
    raster_stores_request = requests.get(
        f'{get_geoserver_url()}/workspaces/{workspace_name}/coveragestores.json',
        auth=(EnvVariable.GEOSERVER_ADMIN_NAME, EnvVariable.GEOSERVER_ADMIN_PASSWORD)
    )
    raster_stores_request.raise_for_status()
    response_data = raster_stores_request.json()
    # Parse JSON structure to get list of feature names
    top_layer_node = response_data["coverageStores"]
    # defaults to empty list if no layers exist
    layers = top_layer_node["coverageStore"] if top_layer_node else []
    layer_names = [layer["name"] for layer in layers]

    return layer_names
