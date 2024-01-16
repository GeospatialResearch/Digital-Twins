"""
Takes generated models and adds them to GeoServer so they can be retrieved by API calls by the frontend
or other clients
"""

import logging
import os
import pathlib
import shutil
from http import HTTPStatus

import rasterio as rio
import requests
import xarray as xr

from src.config import get_env_variable

log = logging.getLogger(__name__)


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
    new_name = f"{nc_file_path.stem}.tif"
    log.info(f"Converting {nc_file_path.name} to {new_name}")
    temp_dir = pathlib.Path("tmp/gtiff")
    # Create temporary storage folder if it does not already exist
    temp_dir.mkdir(parents=True, exist_ok=True)
    gtiff_filepath = temp_dir / new_name
    # Convert the max depths to geo tiff
    with xr.open_dataset(nc_file_path, decode_coords="all") as ds:
        ds['hmax_P0'][0].rio.to_raster(gtiff_filepath)
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
    log.info(f"Uploading {gtiff_filepath.name} to Geoserver workspace {workspace_name}")


    # Set file copying src and dest
    geoserver_data_root = get_env_variable("DATA_DIR_GEOSERVER", cast_to=pathlib.Path)
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
        headers={"Content-type": "text/xml"},
        data=data,
        auth=(get_env_variable("GEOSERVER_ADMIN_NAME"), get_env_variable("GEOSERVER_ADMIN_PASSWORD")),
    )
    if not response.ok:
        # Raise error manually so we can configure the text
        raise requests.HTTPError(response.text, response=response)


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
        # Raise error manually so we can configure the text
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


def create_workspace_if_not_exists(workspace_name: str) -> None:
    """
    Creates a geoserver workspace if it does not currently exist.

    Parameters
    ----------
    workspace_name : str
        The name of the workspace to create if it does not exists.

    Returns
    -------
    None
        This function does not return anything.
    """
    # Create data directory for workspace if it does not already exist
    geoserver_data_root = get_env_variable("DATA_DIR_GEOSERVER", cast_to=pathlib.Path)
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
        auth=(get_env_variable("GEOSERVER_ADMIN_NAME"), get_env_variable("GEOSERVER_ADMIN_PASSWORD"))
    )
    if response.status_code == HTTPStatus.CREATED:
        log.info(f"Created new workspace {workspace_name}.")
    elif response.status_code == HTTPStatus.CONFLICT:
        log.info(f"Workspace {workspace_name} already exists.")
    else:
        # If it does not meet the expected results then raise an error
        # Raise error manually so we can configure the text
        raise requests.HTTPError(response.text, response=response)


def create_datastore_layer(workspace_name, data_store_name: str, layer_name, metadata_elem: str = "") -> None:
    db_exists_response = requests.get(
        f'{get_geoserver_url()}/workspaces/{workspace_name}/datastores/{data_store_name}/featuretypes.json',
        auth=(get_env_variable("GEOSERVER_ADMIN_NAME"), get_env_variable("GEOSERVER_ADMIN_PASSWORD")),
    )
    response_data = db_exists_response.json()
    # Parse JSON structure to get list of feature names
    top_layer_node = response_data["featureTypes"]
    # defaults to empty list if no layers exist
    layers = top_layer_node["featureType"] if top_layer_node else []
    layer_names = [layer["name"] for layer in layers]
    if layer_name in layer_names:
        # If the layer already exists, we don't have to add it again, and can instead return
        return
    # Construct new layer request
    data = f"""
        <featureType>
            <name>{layer_name}</name>
            <title>{layer_name}</title>
            <srs>EPSG:2193</srs>
            <nativeBoundingBox>
                <minx>1569250.25</minx>
                <maxx>1576146.125</maxx>
                <miny>5193063.0</miny>
                <maxy>5198796.5</maxy>
                <crs class="projected">EPSG:2193</crs>
            </nativeBoundingBox>
            <latLonBoundingBox>
                <minx>172.6201769738012</minx>
                <maxx>172.70560400234294</maxx>
                <miny>-43.41493996360092</miny>
                <maxy>-43.36306275550463</maxy>
                <crs>EPSG:4326</crs>
            </latLonBoundingBox>
            <store>
                <class>dataStore</class>
                <name>{data_store_name}</name>
            </store>
            {metadata_elem}
        </featureType>
        """

    response = requests.post(
        f"{get_geoserver_url()}/workspaces/{workspace_name}/datastores/{data_store_name}/featuretypes",
        params={"configure": "all"},
        headers={"Content-type": "text/xml"},
        data=data,
        auth=(get_env_variable("GEOSERVER_ADMIN_NAME"), get_env_variable("GEOSERVER_ADMIN_PASSWORD")),
    )
    if response.status_code == HTTPStatus.CREATED:
        log.info(f"Created new datastore layer {workspace_name}:{layer_name}.")
    else:
        # If it does not meet the expected results then raise an error
        # Raise error manually so we can configure the text
        raise requests.HTTPError(response.text, response=response)


def create_building_layers(workspace_name: str, data_store_name: str) -> None:
    """
    Creates dynamic geoserver layers "nz_building_outlines" and "building_flood_status" for the given workspace.
    If they already exist then does nothing.
    "building_flood_status" required viewparam=scenario:{model_id} to dynamically fetch correct flood statuses.

    Parameters
    ----------
    workspace_name : str
        The name of the workspace to create views for

    Returns
    -------
    None
        This function does not return anything
    """
    # Simple layer that is just displaying the nz_building_outlines database table
    create_datastore_layer(workspace_name, data_store_name, layer_name="nz_building_outlines")

    # More complex layer that has to do dynamic sql queries against model output ID to fetch
    flood_status_layer_name = "building_flood_status"
    flood_status_xml_query = f"""
      <metadata>
        <entry key="JDBC_VIRTUAL_TABLE">
          <virtualTable>
            <name>{flood_status_layer_name}</name>
            <sql>
                SELECT * &#xd;
                FROM nz_building_outlines&#xd;
                LEFT OUTER JOIN (&#xd;
                    SELECT *&#xd;
                    FROM building_flood_status&#xd;
                    WHERE flood_model_id=%scenario%&#xd;
                ) AS flood_statuses&#xd;
                USING (building_outline_id)&#xd;
                WHERE building_outline_lifecycle ILIKE &apos;current&apos;
            </sql>
            <escapeSql>false</escapeSql>
            <geometry>
              <name>geometry</name>
              <type>Polygon</type>
              <srid>2193</srid>
            </geometry>
            <parameter>
              <name>scenario</name>
              <defaultValue>-1</defaultValue>
              <regexpValidator>^(-)?[\d]+$</regexpValidator>
            </parameter>
          </virtualTable>
        </entry>
      </metadata>
    """
    create_datastore_layer(workspace_name, data_store_name, layer_name="building_flood_status", metadata_elem=flood_status_xml_query)


def create_db_store_if_not_exists(db_name: str, workspace_name: str, new_data_store_name: str) -> None:
    """
    Creates PostGIS database store in a geoserver workspace for a given database.
    If it already exists, does not do anything.

    Parameters
    ----------
    workspace_name : str
        The name of the workspace to create views for

    Returns
    -------
    None
        This function does not return anything
    """
    # Create request to check if database store already exists
    db_exists_response = requests.get(
        f'{get_geoserver_url()}/workspaces/{workspace_name}/datastores',
        auth=(get_env_variable("GEOSERVER_ADMIN_NAME"), get_env_variable("GEOSERVER_ADMIN_PASSWORD")),
    )
    response_data = db_exists_response.json()

    # Parse JSON structure to get list of data store names
    top_data_store_node = response_data["dataStores"]
    # defaults to empty list if no data stores exist
    data_stores = top_data_store_node["dataStore"] if top_data_store_node else []
    data_store_names = [data_store["name"] for data_store in data_stores]

    if new_data_store_name in data_store_names:
        # If the data store already exists we don't have to do anything
        return

    # Create request to create database store
    create_db_store_data = f"""
        <dataStore>
          <name>{new_data_store_name}</name>
          <connectionParameters>
            <host>db_postgres</host>
            <port>5432</port>
            <database>{db_name}</database>
            <user>{get_env_variable("POSTGRES_USER")}</user>
            <passwd>{get_env_variable("POSTGRES_PASSWORD")}</passwd>
            <dbtype>postgis</dbtype>
          </connectionParameters>
        </dataStore>
        """
    # Send request to add datastore
    response = requests.post(
        f'{get_geoserver_url()}/workspaces/{workspace_name}/datastores',
        params={"configure": "all"},
        headers={"Content-type": "text/xml"},
        data=create_db_store_data,
        auth=(get_env_variable("GEOSERVER_ADMIN_NAME"), get_env_variable("GEOSERVER_ADMIN_PASSWORD")),
    )
    if response.status_code == HTTPStatus.CREATED:
        log.info(f"Created new db store {workspace_name}.")
    # Expected responses are CREATED if the new store is created or CONFLICT if one already exists.
    else:
        # If it does not meet the expected results then raise an error
        # Raise error manually so we can configure the text
        raise requests.HTTPError(response.text, response=response)


def create_building_database_views_if_not_exists() -> None:
    """
    Creates a geoserver workspace and building layers using database views if they do not currently exist.
    These only need to be created once per database.

    Returns
    -------
    None
        This function does not return anything.
    """
    log.debug("Creating building database views if they do not exist")
    db_name = get_env_variable("POSTGRES_DB")
    workspace_name = f"{db_name}-buildings"
    # Create workspace if it doesn't exist, so that the namespaces can be separated if multiple dbs are running
    create_workspace_if_not_exists(workspace_name)
    # Create a new database store if geoserver is not yet configured for that database
    data_store_name = f"{db_name} PostGIS"
    create_db_store_if_not_exists(db_name, workspace_name, data_store_name)
    # Create SQL view layers so geoserver can dynamically serve building layers based on model outputs.
    create_building_layers(workspace_name, data_store_name)


def add_model_output_to_geoserver(model_output_path: pathlib.Path, model_id: int) -> None:
    """
    Adds the model output max depths to GeoServer, ready for serving.
    The GeoServer layer name will be f"Output_{model_id}" and the workspace name will be "{db_name}-dt-model-outputs"

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
    log.debug("Adding model output to geoserver")
    gtiff_filepath = convert_nc_to_gtiff(model_output_path)
    db_name = get_env_variable("POSTGRES_DB")
    # Assign a new workspace name based on the db_name, to prevent name clashes if running multiple databases
    workspace_name = f"{db_name}-dt-model-outputs"
    create_workspace_if_not_exists(workspace_name)
    add_gtiff_to_geoserver(gtiff_filepath, workspace_name, model_id)
