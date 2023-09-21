"""
Takes generated models and adds them to GeoServer so they can be retrieved by API calls by the frontend
or other clients
"""

import os
import pathlib
import shutil

import rasterio as rio
import requests
import xarray as xr

from src.config import get_env_variable

GEOSERVER_REST_URL = "http://localhost:8088/geoserver/rest/"


def convert_nc_to_gtiff(nc_file_path: pathlib.Path) -> pathlib.Path:
    """
    Creates a GeoTiff file from a netCDF model output. The Tiff represents the max flood height in the model output.

    Parameters
    ----------
    nc_file_path : pathlib.Patj
        The file path to the netCDF file.

    Returns
    -------
    pathlib.Path
        The filepath of the new GeoTiff file.
    """
    name = nc_file_path.stem
    new_name = f"{name}.tif"
    temp_dir = pathlib.Path("tmp/gtiff")
    # Create temporary storage folder if it does not already exist
    temp_dir.mkdir(parents=True, exist_ok=True)
    gtiff_filepath = temp_dir / new_name
    # Convert the max depths to geo tiff
    with xr.open_dataset(nc_file_path, decode_coords="all") as ds:
        ds['hmax_P0'].rio.to_raster(gtiff_filepath)
    return pathlib.Path(os.getcwd()) / gtiff_filepath


def upload_gtiff_to_store(
        geoserver_url: str, gtiff_filepath: pathlib.Path, store_name: str, workspace_name: str) -> None:
    """
    Uploads a GeoTiff file to a new GeoServer store, to enable serving.

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

    Returns
    -------
    None
        This function does not return anything
    """
    # Copy file to geoserver data folder
    geoserver_data_root = pathlib.Path("geoserver/geoserver_data")
    geoserver_data_dest = pathlib.Path("data") / gtiff_filepath.name
    shutil.copy(gtiff_filepath, geoserver_data_root / geoserver_data_dest)
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
        headers={"Content-type": "text/xml"},
        data=data,
        auth=(get_env_variable("GEOSERVER_ADMIN_NAME"), get_env_variable("GEOSERVER_ADMIN_PASSWORD")),
    )
    # Raise exception if request fails.
    response.raise_for_status()


def create_layer_from_store(geoserver_url: str, layer_name: str, native_crs: str, workspace_name: str) -> None:
    """
    Creates a GeoServer Layer from a GeoServer store, making it ready to serve.

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

    Returns
    -------
    None
        This function does not return anything
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
        headers={"Content-type": "text/xml"},
        data=data,
        auth=(get_env_variable("GEOSERVER_ADMIN_NAME"), get_env_variable("GEOSERVER_ADMIN_PASSWORD")),
    )
    if not response.ok:
        raise requests.HTTPError(response.text, response=response)


def get_geoserver_url() -> str:
    """
    Retrieves full GeoServer URL from environment variables.

    Returns
    -------
    str
        The full GeoServer URL
    """
    gs_host = get_env_variable("GEOSERVER_HOST")
    gs_port = get_env_variable("GEOSERVER_PORT")
    return f"{gs_host}:{gs_port}/geoserver/rest"


def add_gtiff_to_geoserver(gtiff_filepath: pathlib.Path, workspace_name: str, model_id: int) -> None:
    """
    Uploads a GeoTiff file to GeoServer, ready for serving to clients.

    Parameters
    ----------
    gtiff_filepath : pathlib.Path
        The filepath to the GeoTiff file to be served.
    workspace_name : str
        The name of the existing GeoServer workspace that the store is to be added to.
    model_id : int
        The id of the model being added, to facilitate layer naming.

    Returns
    -------
    None
        This function does not return anything
    """
    gs_url = get_geoserver_url()
    layer_name = f"output_{model_id}"
    with rio.open(gtiff_filepath) as gtiff:
        gtiff_crs = gtiff.crs.wkt
    upload_gtiff_to_store(gs_url, gtiff_filepath, layer_name, workspace_name)
    gtiff_filepath.unlink()
    create_layer_from_store(gs_url, layer_name, gtiff_crs, workspace_name)


def add_model_output_to_geoserver(model_output_path: pathlib.Path, model_id: int):
    """
    Adds the model output max depths to GeoServer, ready for serving.
    The GeoServer layer name will be f"Output_{model_id}" and the workspace name will be "dt-model-outputs"

    Parameters
    ----------
    model_output_path : pathlib.Path
        The file path to the model output to serve.
    model_id : int
        The database id of the model output.

    Returns
    -------
    None
        This function does not return anything
    """
    gtiff_filepath = convert_nc_to_gtiff(model_output_path)
    add_gtiff_to_geoserver(gtiff_filepath, "dt-model-outputs", model_id)

# def add_flooded_buildings_to_geoserver(flooded_buildings: gpd.GeoDataFrame, model_id: str):
#     """"""
#     layer_name = f"buildings_{model_id}"
#     buildings_crs = flooded_buildings.crs.wkt
#
#     # Save file to disk to be read my geoserver
#     temp_dir = pathlib.Path("tmp/geojson")
#     # Create temporary storage folder if it does not already exist
#     temp_dir.mkdir(parents=True, exist_ok=True)
#     geojson_path = temp_dir / f"{layer_name}.geojson"
#     flooded_buildings.to_file("geojson_filepath", crs=buildings_crs)
#
#     gs_url = get_geoserver_url()
#     upload_geojson_to_store(gs_url, geojson_path, layer_name, workspace_name)
#     create_layer_from_store(gs_url, layer_name, buildings_crs, workspace_name)
