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

"""
Takes generated models and adds them to GeoServer so they can be retrieved by API calls by the frontend
or other clients.
"""

import logging
import os
import pathlib
from xml.sax import saxutils

import xarray as xr

from src import geoserver
from src.config import EnvVariable

log = logging.getLogger(__name__)
_xml_header = {"Content-type": "text/xml"}


def convert_nc_to_geoserver_compatible(orig_nc_file_path: pathlib.Path) -> pathlib.Path:
    """
    Create a geoserver compliant netCDF file from a netCDF model output.
    Following compliance from COARDS convention.
        https://docs.geoserver.org/latest/en/user/extensions/netcdf/netcdf.html#notes-on-supported-netcdfs

    Parameters
    ----------
    orig_nc_file_path : pathlib.Path
        The file path to the netCDF file.

    Returns
    -------
    pathlib.Path
        The filepath of the new compliant netCDF file.
    """
    log.info(f"Converting {orig_nc_file_path.name} to geoserver compliant netCDF file.")
    temp_dir = pathlib.Path("tmp/gtiff")
    # Create temporary storage folder if it does not already exist
    temp_dir.mkdir(parents=True, exist_ok=True)
    compliant_nc_path = temp_dir / orig_nc_file_path.name
    # Convert the netcdf to WGS84, COARDS compliant coordinates
    with xr.open_dataset(orig_nc_file_path, decode_coords="all") as ds:
        ds = ds.drop_vars(["blockid", "blockxo", "blockyo", "blockwidth", "blocklevel", "blockstatus"])
        wgs84_crs_code = 4326
        ds_wgs84 = ds.rio.reproject(f"EPSG:{wgs84_crs_code}")
        ds_wgs84.rio.write_crs(wgs84_crs_code, inplace=True)
        ds_wgs84.to_netcdf(compliant_nc_path)

    return pathlib.Path(os.getcwd()) / compliant_nc_path


def convert_nc_to_gtiff(nc_file_path: pathlib.Path) -> pathlib.Path:
    """
    Create a GeoTiff file from a netCDF model output. The TIFF represents the max flood height in the model output.

    Parameters
    ----------
    nc_file_path : pathlib.Path
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


def create_building_layers(workspace_name: str, data_store_name: str) -> None:
    """
    Create dynamic GeoServer layers "nz_building_outlines" and "building_flood_status" for the given workspace.
    If they already exist then do nothing.
    "building_flood_status" requires viewparam=scenario:{model_id} to dynamically fetch correct flood statuses.

    Parameters
    ----------
    workspace_name : str
        The name of the workspace to create views for.
    data_store_name : str
         The name of the datastore that the building layer is being created from.

    Raises
    ----------
    HTTPError
        If geoserver responds with an error, raises it as an exception since it is unexpected.
    """
    # Simple layer that is just displaying the nz_building_outlines database table
    geoserver.create_datastore_layer(workspace_name, data_store_name, layer_name="nz_building_outlines")

    # More complex layer that has to do dynamic sql queries against model output ID to fetch
    flood_status_layer_name = "building_flood_status"
    flooded_buildings_sql_query = """
        SELECT *,
               is_flooded::int AS is_flooded_int,
               4.5             AS extruded_height,
               CASE
                   WHEN is_flooded THEN 'darkred'
                   ELSE 'darkgreen'
               END             AS fill
        FROM nz_building_outlines
                 LEFT OUTER JOIN building_flood_status USING (building_outline_id)
        WHERE building_outline_lifecycle ILIKE 'current'
        AND flood_model_id=%scenario%
    """
    xml_escaped_sql = saxutils.escape(flooded_buildings_sql_query, entities={r"'": "&apos;", "\n": "&#xd;"})

    flood_status_xml_query = rf"""
      <metadata>
        <entry key="JDBC_VIRTUAL_TABLE">
          <virtualTable>
            <name>{flood_status_layer_name}</name>
            <sql>
                {xml_escaped_sql}
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
    geoserver.create_datastore_layer(workspace_name,
                                     data_store_name,
                                     layer_name="building_flood_status",
                                     metadata_elem=flood_status_xml_query)


def create_viridis_style_if_not_exists() -> None:
    """Create a GeoServer style for flood rasters using the viridis color scale."""
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
    with open('eddie_floodresilience/flood_model/templates/viridis_raster.sld', 'rb') as payload:
        sld_response = requests.put(
            f'{get_geoserver_url()}/styles/{style_name}',
            data=payload,
            headers={"Content-type": "application/vnd.ogc.sld+xml"},
            auth=(EnvVariable.GEOSERVER_ADMIN_NAME, EnvVariable.GEOSERVER_ADMIN_PASSWORD)
        )
    sld_response.raise_for_status()
    log.info(f"Style '{style_name}.sld' created.")


def create_building_database_views_if_not_exists() -> None:
    """
    Create a GeoServer workspace and building layers using database views if they do not currently exist.
    These only need to be created once per database.
    """
    log.debug("Creating building database views if they do not exist")
    db_name = EnvVariable.POSTGRES_DB
    workspace_name = f"{db_name}-buildings"
    # Create workspace if it doesn't exist, so that the namespaces can be separated if multiple dbs are running
    geoserver.create_workspace_if_not_exists(workspace_name)
    # Create a new database store if geoserver is not yet configured for that database
    data_store_name = f"{db_name} PostGIS"
    geoserver.create_db_store_if_not_exists(db_name, workspace_name, data_store_name)
    # Create SQL view layers so geoserver can dynamically serve building layers based on model outputs.
    create_building_layers(workspace_name, data_store_name)


def add_model_output_to_geoserver(model_output_path: pathlib.Path, model_id: int) -> None:
    """
    Add the model output max depths to GeoServer, ready for serving.
    The GeoServer layer name will be f"Output_{model_id}" and the workspace name will be "{db_name}-dt-model-outputs"

    Parameters
    ----------
    model_output_path : pathlib.Path
        The file path to the model output to serve.
    model_id : int
        The database id of the model output.
    """
    log.debug("Adding model output to geoserver")
    nc_filepath = convert_nc_to_geoserver_compatible(model_output_path)
    db_name = EnvVariable.POSTGRES_DB
    # Assign a new workspace name based on the db_name, to prevent name clashes if running multiple databases
    workspace_name = f"{db_name}-dt-model-outputs"
    geoserver.create_workspace_if_not_exists(workspace_name)
    band_name = "h_P0"  # The band for water depth
    # Upload NetCDF output file to Geoserver, creating a layer for water depth
    geoserver.add_nc_to_geoserver(nc_filepath, band_name, workspace_name, model_id)
    # Delete temporary file
    nc_filepath.unlink()
    # Ensure styling for the layer is present in geoserver
    create_viridis_style_if_not_exists()
