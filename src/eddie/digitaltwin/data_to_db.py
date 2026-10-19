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

"""
This script fetches geospatial data from the data providers registered in 'eddie.digitaltwin.provider_registry'
(e.g. the core 'ogc_wfs'/'arcgis_rest' providers, or the 'geoapis'-based providers registered by the optional
modules, i.e. 'eddie.digitaltwin.nz_providers') and stores it in the database. It also saves user log
information in the database.
"""

import logging
import pathlib
from datetime import datetime, timezone
from typing import Set, Tuple

import geopandas as gpd
import pandas as pd
from sqlalchemy import insert, update
from sqlalchemy.engine import Connection
from sqlalchemy.sql import text

from eddie.digitaltwin.instructions_records_to_db import FetchMode, GeospatialLayers, parse_cache_length
from eddie.digitaltwin.provider_registry import get_provider
from eddie.digitaltwin.tables import UserLogInfo, check_table_exists, create_table
import eddie.geoserver as gs

log = logging.getLogger(__name__)


class NoNonIntersectionError(Exception):
    """Exception raised when no non-intersecting area is found."""


def get_full_geospatial_layers(conn: Connection) -> pd.DataFrame:
    """
    Retrieve geospatial layers from the database that have fetch_mode full.

    Parameters
    ----------
    conn : Connection
        The connection used to connect to the database.

    Returns
    -------
    pd.DataFrame
        Data frame containing geospatial layers that have a fetch_mode full, including 'cache_length',
        'refresh_after' and 'fetched_at' so callers can determine whether a layer's cached data has expired.
    """
    # SQL query to retrieve geospatial layers that have fetch_mode full
    full_geo_query = f"""
    SELECT *
    FROM {GeospatialLayers.__tablename__}
    WHERE fetch_mode = '{FetchMode.FULL}' AND unique_column_name IS NULL;
    """
    # Retrieve geospatial layers using the provided SQL query
    full_geo_layers = pd.read_sql(full_geo_query, conn)
    # Drop the 'unique_id' column from the DataFrame
    full_geo_layers = full_geo_layers.drop(columns=['unique_id'])
    return full_geo_layers


def get_aoi_geospatial_layers(conn: Connection) -> pd.DataFrame:
    """
    Retrieve geospatial layers from the database that have fetch_mode aoi.

    Parameters
    ----------
    conn : Connection
        The connection used to connect to the database.

    Returns
    -------
    pd.DataFrame
        Data frame containing geospatial layers that have fetch_mode aoi, including 'cache_length' so callers can
        determine the expiry to record against newly logged catchment areas in 'user_log_information'.
    """
    # SQL query to retrieve geospatial layers that have fetch_mode aoi
    aoi_query = f"""
    SELECT *
    FROM {GeospatialLayers.__tablename__}
    WHERE unique_column_name IS NOT NULL AND fetch_mode = '{FetchMode.AOI}';
    """
    # Retrieve geospatial layers using the provided SQL query
    aoi_geo_layers = pd.read_sql(aoi_query, conn)
    # Drop the 'unique_id' column from the DataFrame
    aoi_geo_layers = aoi_geo_layers.drop(columns=['unique_id'])
    return aoi_geo_layers


def get_geospatial_layer_info(layer_row: pd.Series) -> Tuple[str, str, str, str]:
    """
    Extract geospatial layer information from a single layer entry.

    Parameters
    ----------
    layer_row : pd.Series
        A geospatial layer row that represents a single geospatial layer along with its associated information.

    Returns
    -------
    Tuple[str, str, str, str]
        A tuple containing the values for data_provider, layer_id, table_name, and unique_column_name.
    """
    # Extract information from the single layer entry
    data_provider = layer_row['data_provider']
    layer_id = layer_row['layer_id']
    table_name = layer_row["table_name"]
    unique_column_name = layer_row['unique_column_name']
    return data_provider, layer_id, table_name, unique_column_name


def get_vector_data_id_not_in_db(
    conn: Connection,
    vector_data: gpd.GeoDataFrame,
    table_name: str,
    unique_column_name: str,
    area_of_interest: gpd.GeoDataFrame
) -> Set[int]:
    """
    Get the IDs from the fetched vector_data that are not present in the specified database table
    for the area of interest.

    Parameters
    ----------
    conn : Connection
        The connection used to connect to the database.
    vector_data : gpd.GeoDataFrame
        A GeoDataFrame containing the fetched vector data.
    table_name : str
        The name of the table in the database.
    unique_column_name : str
        The name of the unique column in the table.
    area_of_interest : gpd.GeoDataFrame
        A GeoDataFrame representing the area of interest.

    Returns
    -------
    Set[int]
        The set of IDs from the fetched vector_data that are not present in the specified table in the database.
    """
    # Get the unique IDs from the vector_data
    vector_data_ids = set(vector_data[unique_column_name])
    # Fetch the unique IDs from the specified table that intersect with the area of interest
    aoi_polygon = area_of_interest["geometry"][0]
    # The AOI is in the CRS it came with, else EPSG:4326. It is transformed into the stored table's CRS.
    aoi_srid = (area_of_interest.crs.to_epsg() if area_of_interest.crs is not None else None) or 4326
    command_text = f"""
    SELECT DISTINCT {unique_column_name}
    FROM {table_name} AS ids
    WHERE ST_Intersects(
        ids.geometry,
        ST_Transform(ST_GeomFromText(:aoi_polygon, :aoi_srid), Find_SRID('public', :table_name, 'geometry'))
    );
    """
    query = text(command_text).bindparams(
        aoi_polygon=str(aoi_polygon),
        aoi_srid=aoi_srid,
        table_name=table_name
    )
    # Execute the query and retrieve the IDs present in the database
    ids_in_db = set(pd.read_sql(query, conn)[unique_column_name])
    # Find the IDs from vector_data that are not present in the database
    ids_not_in_db = vector_data_ids - ids_in_db
    return ids_not_in_db


def is_refresh_expired(refresh_after: pd.Timestamp | None) -> bool:
    """
    Determine whether a 'refresh_after' expiry date has passed, meaning the cached data it covers is stale and
    should be re-fetched. Data without a 'refresh_after' never expires.

    Parameters
    ----------
    refresh_after : pd.Timestamp | None
        The expiry date, or None/NaT if the data never expires.

    Returns
    -------
    bool
        True if 'refresh_after' is set and has passed, False otherwise.
    """
    if pd.isna(refresh_after):
        return False
    return datetime.now(timezone.utc) >= refresh_after


def update_fetched_at(conn: Connection, data_provider: str, layer_id: str) -> None:
    """
    Record the current time as the 'fetched_at' timestamp for a geospatial layer, after its data has been fetched.
    Used for both 'full' and 'aoi' fetch_mode layers.

    Parameters
    ----------
    conn : Connection
        The connection used to connect to the database.
    data_provider : str
        The data provider of the geospatial layer.
    layer_id : str
        The ID of the geospatial layer.
    """
    conn.execute(
        update(GeospatialLayers)
        .where(GeospatialLayers.data_provider == data_provider, GeospatialLayers.layer_id == layer_id)
        .values(fetched_at=datetime.now(timezone.utc))
    )


def update_full_layer_cache_expiry(
    conn: Connection, data_provider: str, layer_id: str, cache_length: str | None
) -> None:
    """
    Record the current time as 'fetched_at' and recompute 'refresh_after' from 'cache_length', for a 'full'
    fetch_mode geospatial layer, after its data has been fetched. Only valid for 'full' fetch_mode layers, since
    'refresh_after' on 'geospatial_layers' is constrained to those; 'aoi' fetch_mode layers instead have their
    expiry recorded per logged catchment area on 'user_log_information.refresh_after' (see 'user_log_info_to_db').

    Parameters
    ----------
    conn : Connection
        The connection used to connect to the database.
    data_provider : str
        The data provider of the geospatial layer.
    layer_id : str
        The ID of the geospatial layer.
    cache_length : str | None
        The duration offset (e.g. "1y", "2w3d", "15d") configured for the layer, or None if it never expires.
    """
    fetched_at = datetime.now(timezone.utc)
    refresh_after = fetched_at + parse_cache_length(cache_length) if cache_length else None
    conn.execute(
        update(GeospatialLayers)
        .where(GeospatialLayers.data_provider == data_provider, GeospatialLayers.layer_id == layer_id)
        .values(fetched_at=fetched_at, refresh_after=refresh_after)
    )


def full_geospatial_layers_data_to_db(
    conn: Connection,
    crs: int,
) -> None:
    """
    Fetch full geospatial layers data using the registered 'data_provider' for each layer and store it into the
    database. A layer already present in the database is only re-fetched if its 'refresh_after' expiry date has
    passed.

    Parameters
    ----------
    conn : Connection
        The connection used to connect to the database.
    crs : int
        The coordinate reference system (CRS) code to use.
    """
    # Get full fetch mode geospatial layers
    full_geo_layers = get_full_geospatial_layers(conn)

    workspace_name = gs.Workspaces.INPUT_LAYERS_WORKSPACE
    data_store = gs.create_main_db_store(workspace_name)
    # Iterate over each full geospatial layer
    for _, layer_row in full_geo_layers.iterrows():
        # Extract geospatial layer information
        data_provider, layer_id, table_name, _ = get_geospatial_layer_info(layer_row)

        # Check if the table already exists in the database, and whether it has expired and needs re-fetching
        table_exists = check_table_exists(conn, table_name)
        expired = is_refresh_expired(layer_row.get('refresh_after'))
        if table_exists and not expired:
            log.info(f"'{table_name}' data already exists in the database.")
            continue
        if table_exists and expired:
            log.info(f"'{table_name}' data has passed its 'refresh_after' expiry date. Re-fetching.")

        # Fetch vector data using the registered provider for this layer's 'data_provider'
        log.info(f"Fetching '{table_name}' data ({data_provider} {layer_id}).")
        vector_data = get_provider(data_provider)(layer_id, None, crs)
        # Insert vector data into the database, replacing any existing (expired) table of the same name
        log.info(f"Adding '{table_name}' data ({data_provider} {layer_id}) to the database.")
        vector_data.to_postgis(table_name, conn, index=False, if_exists="replace")
        gs.create_datastore_layer(workspace_name, data_store, table_name)
        # Record when this layer's data was fetched, and recompute its 'refresh_after' expiry from 'cache_length'
        update_full_layer_cache_expiry(conn, data_provider, layer_id, layer_row.get('cache_length'))


def create_user_log_table(conn: Connection) -> None:
    """
    Create the 'user_log_information' table if it doesn't exist.
    A table left over from an older version that stores another SRID is discarded first. It only records which areas
    have been fetched, so the cost is fetching each layer once more.

    Parameters
    ----------
    conn : Connection
        The connection used to connect to the database.
    """
    srid_query = text("SELECT srid FROM geometry_columns WHERE f_table_name = :table_name")
    stored_srid = conn.execute(srid_query, {"table_name": UserLogInfo.__tablename__}).scalar()
    if stored_srid not in (None, UserLogInfo.geometry.type.srid):
        log.info(f"Discarding '{UserLogInfo.__tablename__}' stored in SRID {stored_srid}.")
        UserLogInfo.__table__.drop(bind=conn)
    create_table(conn, UserLogInfo)


def get_non_intersection_area_from_db(
    conn: Connection,
    catchment_area: gpd.GeoDataFrame,
    table_name: str
) -> gpd.GeoDataFrame:
    """
    Get the non-intersecting area from the catchment area and user log information table in the database
    for the specified table. A previously logged area whose 'refresh_after' expiry date has passed is not
    counted as covered, so its area is included in the non-intersecting area and its data is re-fetched.

    Parameters
    ----------
    conn : Connection
        The connection used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    table_name : str
        The name of the table in the database.

    Returns
    -------
    gpd.GeoDataFrame
        The non-intersecting area, or the original catchment area if no intersections are found.

    Raises
    ------
    NoNonIntersectionError
        If the non-intersecting area is empty, it suggests that the catchment area is already fully covered.
    """
    # Create the 'user_log_information' table if it doesn't exist
    create_user_log_table(conn)
    # Extract the geometry of the catchment area, in the CRS of the user log table
    user_log_srid = UserLogInfo.geometry.type.srid
    catchment_in_log_crs = catchment_area.to_crs(user_log_srid)
    catchment_wkt = catchment_in_log_crs.geometry[0].wkt
    # Build the SQL query to find intersections between the user log information and the catchment area.
    # Only unexpired log entries count as already covering their area; an expired entry's area is excluded here,
    # so it is folded back into the non-intersecting area and its data gets re-fetched.
    command_text = f"""
    SELECT *
    FROM {UserLogInfo.__tablename__}
    WHERE :table_name = ANY(source_table_list)
    AND (refresh_after IS NULL OR refresh_after > now())
    AND ST_Intersects(geometry, ST_GeomFromText(:catchment_polygon, :user_log_srid));
    """
    query = text(command_text).bindparams(
        table_name=table_name,
        catchment_polygon=catchment_wkt,
        user_log_srid=user_log_srid
    )
    # Execute the SQL query and retrieve the intersections as a GeoDataFrame
    user_log_intersections = gpd.GeoDataFrame.from_postgis(query, conn, geom_col="geometry")
    # Check if there are no intersections
    if user_log_intersections.empty:
        return catchment_area
    # Compute the non-intersecting area in the CRS the user log is stored in, so that an area logged before matches
    # exactly; reprojecting the log into the catchment CRS instead leaves slivers from rounding
    non_intersection_area = catchment_in_log_crs.overlay(user_log_intersections, how='difference')
    # Check if the non-intersecting area is empty
    if non_intersection_area.empty:
        raise NoNonIntersectionError(
            f"'{table_name}' data for the requested catchment area is already in the database.")
    return non_intersection_area.to_crs(catchment_area.crs)


def process_new_aoi_geospatial_layers(
    conn: Connection,
    data_provider: str,
    layer_id: str,
    table_name: str,
    area_of_interest: gpd.GeoDataFrame,
    crs: int,
) -> None:
    """
    Fetch new aoi geospatial layers data using the registered 'data_provider' and store it into the database.

    Parameters
    ----------
    conn : Connection
        The connection used to connect to the database.
    data_provider : str
        The data provider of the geospatial layer.
    layer_id : str
        The ID of the geospatial layer.
    table_name : str
        The database table name of the geospatial layer.
    area_of_interest : gpd.GeoDataFrame
        A GeoDataFrame representing the area of interest.
    crs : int
        The coordinate reference system (CRS) code to use.
    """
    # Fetch vector data using the registered provider for this layer's 'data_provider'
    log.info(f"Fetching '{table_name}' data ({data_provider} {layer_id}) for the catchment area.")
    vector_data = get_provider(data_provider)(layer_id, area_of_interest, crs)
    # Check if the fetched vector data is empty
    if vector_data.empty:
        log.info(f"The requested catchment area does not contain any '{table_name}' data ({data_provider} {layer_id}).")
    else:
        # Insert vector data into the database
        log.info(f"Adding '{table_name}' data ({data_provider} {layer_id}) for the catchment area to the database.")
        vector_data.to_postgis(table_name, conn, index=False, if_exists="replace")
        # Serve data with geoserver
        workspace_name = gs.Workspaces.INPUT_LAYERS_WORKSPACE
        data_store = gs.create_main_db_store(workspace_name)
        gs.create_datastore_layer(workspace_name, data_store, table_name)
        # Record when this layer's data was fetched
        update_fetched_at(conn, data_provider, layer_id)


def process_existing_aoi_geospatial_layers(
    conn: Connection,
    data_provider: str,
    layer_id: str,
    table_name: str,
    unique_column_name: str,
    area_of_interest: gpd.GeoDataFrame,
    crs: int,
) -> None:
    """
    Fetch existing AOI geospatial layers data using the registered 'data_provider' and store the missing values
    within AOI into the database.
    The 'area_of_interest' passed in is the non-intersecting area from 'get_non_intersection_area_from_db', which
    already excludes any previously logged area that is still within its 'refresh_after' expiry (see
    'user_log_information'); so any area reaching this function is treated as new data to append.

    Parameters
    ----------
    conn : Connection
        The connection used to connect to the database.
    data_provider : str
        The data provider of the geospatial layer.
    layer_id : str
        The ID of the geospatial layer.
    table_name : str
        The database table name of the geospatial layer.
    unique_column_name : str
        The unique column name used for record identification in the database table.
    area_of_interest : gpd.GeoDataFrame
        A GeoDataFrame representing the area of interest.
    crs : int
        The coordinate reference system (CRS) code to use.
    """
    # Fetch vector data using the registered provider for this layer's 'data_provider'
    log.info(f"Fetching '{table_name}' data ({data_provider} {layer_id}) for the catchment area.")
    vector_data = get_provider(data_provider)(layer_id, area_of_interest, crs)
    # Check if the fetched vector data is empty
    if vector_data.empty:
        log.info(f"The requested catchment area does not contain any '{table_name}' data ({data_provider} {layer_id}).")
    else:
        # Get IDs from the vector data that are not in the database
        ids_not_in_db = get_vector_data_id_not_in_db(
            conn, vector_data, table_name, unique_column_name, area_of_interest)
        # Check if there are IDs not in the database
        if ids_not_in_db:
            # Get vector data that contains only the IDs not present in the database
            vector_data_not_in_db = vector_data[vector_data[unique_column_name].isin(ids_not_in_db)]
            # A table keeps the CRS it was created in, so data fetched in another working CRS is reprojected to it
            srid_query = text("SELECT Find_SRID('public', :table_name, 'geometry')")
            table_srid = conn.execute(srid_query, {"table_name": table_name}).scalar()
            vector_data_not_in_db = vector_data_not_in_db.to_crs(table_srid)
            # Insert vector data into the database
            log.info(
                f"Adding new '{table_name}' data ({data_provider} {layer_id}) for the catchment area to the database.")
            vector_data_not_in_db.to_postgis(table_name, conn, index=False, if_exists="append")
            # Refresh the served layer so its bounds include the appended data.
            # ANALYZE first, since GeoServer estimates PostGIS table bounds from the planner statistics.
            conn.execute(text(f'ANALYZE "{table_name}"'))
            workspace_name = gs.Workspaces.INPUT_LAYERS_WORKSPACE
            gs.create_datastore_layer(workspace_name, gs.create_main_db_store(workspace_name), table_name)
            update_fetched_at(conn, data_provider, layer_id)
        else:
            log.info(f"'{table_name}' data for the requested catchment area is already in the database.")


def aoi_geospatial_layers_data_to_db(
    conn: Connection,
    catchment_area: gpd.GeoDataFrame,
    crs: int,
) -> None:
    """
    Fetch AOI based geospatial layers data using the registered 'data_provider' for each layer and store it into
    the database.

    Parameters
    ----------
    conn : Connection
        The connection used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    crs : int
        The coordinate reference system (CRS) code to use.
    """
    # Get aoi geospatial layers from the database
    aoi_geo_layers = get_aoi_geospatial_layers(conn)

    # Iterate over each aoi geospatial layer
    for _, layer_row in aoi_geo_layers.iterrows():
        # Extract geospatial layer information
        data_provider, layer_id, table_name, unique_column_name = get_geospatial_layer_info(layer_row)
        try:
            # Get the non-intersection area of the catchment area
            non_intersection_area = get_non_intersection_area_from_db(conn, catchment_area, table_name)
        except NoNonIntersectionError as error:
            # Log the error and continue to the next layer
            log.info(error)
            continue

        # Check if the table already exists in the database
        if check_table_exists(conn, table_name):
            # Process existing AOI geospatial layers
            process_existing_aoi_geospatial_layers(
                conn, data_provider, layer_id, table_name, unique_column_name, non_intersection_area, crs)
        else:
            # Process new AOI geospatial layers
            process_new_aoi_geospatial_layers(
                conn, data_provider, layer_id, table_name, non_intersection_area, crs)


def store_geospatial_layers_data_to_db(
    conn: Connection,
    catchment_area: gpd.GeoDataFrame,
    crs: int,
) -> None:
    """
    Fetch geospatial layers data using the registered 'data_provider' for each layer and store it into the
    database.

    Parameters
    ----------
    conn : Connection
        The connection used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    crs : int
        The coordinate reference system (CRS) code to use.
    """
    # Store full fetch mode geospatial layers data to the database
    full_geospatial_layers_data_to_db(conn, crs)
    # Store aoi fetch mode geospatial layers data to the database
    aoi_geospatial_layers_data_to_db(conn, catchment_area, crs)
    serve_static_files(conn, pathlib.Path("./src/static/geo"))


def user_log_info_to_db(conn: Connection, catchment_area: gpd.GeoDataFrame) -> None:
    """
    Store user log information to the database. The entry's 'refresh_after' is set to the soonest expiry among the
    aoi layers' 'cache_length' values (i.e. the first layer in 'source_table_list' to need re-fetching), measured
    from now. If none of the layers has a 'cache_length' configured, 'refresh_after' is left as None (never expires).

    Parameters
    ----------
    conn : Connection
        The connection used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    """
    # Create the 'user_log_information' table if it doesn't exist
    create_user_log_table(conn)
    # Get the list of table names for aoi geospatial layers
    aoi_geo_layers = get_aoi_geospatial_layers(conn)
    table_list = aoi_geo_layers["table_name"].tolist()
    # Compute the soonest expiry among the aoi layers' configured 'cache_length' values, if any
    cache_lengths = aoi_geo_layers["cache_length"].dropna()
    refresh_after = (
        datetime.now(timezone.utc) + min(parse_cache_length(cl) for cl in cache_lengths)
        if not cache_lengths.empty else None
    )
    # Get the catchment geometry, in the CRS of the user log table
    catchment_geom = catchment_area.to_crs(UserLogInfo.geometry.type.srid).geometry[0].wkt
    # Create the query object
    query = insert(UserLogInfo).values(
        source_table_list=table_list, refresh_after=refresh_after, geometry=catchment_geom)
    # Execute the query
    conn.execute(query)


def add_vector_file_to_db(conn: Connection, vector_file_path: pathlib.Path) -> str:
    """
    Add a vector file to the database.

    Parameters
    ----------
    conn : Connection
        The connection used to connect to the database.
    vector_file_path : pathlib.Path
        The Path to the vector file.

    Raises
    ------
    KeyError
        Raised if the vector file does not have a correctly defined EPSG# CRS.

    Returns
    -------
    str
        The name of the database table created.
    """
    log.info(f"Adding vector file '{vector_file_path.name}' to the database.")
    # Read the prefix of the file name to make it the table name.
    file_name = vector_file_path.stem
    # Upload the file to the database
    gdf = gpd.read_file(vector_file_path)
    if gdf.crs.to_epsg() is None:
        raise KeyError(f"CRS is not defined in EPSG# form in vector file {vector_file_path}.")
    gdf.to_postgis(file_name, conn, if_exists="replace")
    return file_name


def serve_static_files(conn: Connection, vector_file_directory: pathlib.Path) -> None:
    """
    Add all vector files (.geojson, .shp, .geodb) in directory to db and serve them.

    Parameters
    ----------
    conn : Connection
        The connection used to connect to the database.
    vector_file_directory : pathlib.Path
        The Path to the directory containing the vector files.
    """
    # Only administrators may run WPS processes directly. Safe to repeat on every run.
    gs.restrict_wps_service()
    # Find the set of all served workspaces that deal with static files
    statics = {gs.Workspaces.STATIC_FILES_WORKSPACE, gs.Workspaces.EXTRUDED_LAYERS_WORKSPACE}
    # Find the served workspaces that are not the static ones
    non_statics = set(gs.Workspaces) - statics
    # Serve the static files
    for workspace_name in statics:
        data_store = gs.create_main_db_store(workspace_name)
        if workspace_name == gs.Workspaces.EXTRUDED_LAYERS_WORKSPACE:
            # Extruded files are stored in another directory to help manage them
            directory = vector_file_directory / "3d"
        else:
            directory = vector_file_directory
        if not directory.exists():
            log.warning(f"Directory '{directory}' does not exist. Cannot serve static files from '{directory}'.")
            continue
        for file in directory.iterdir():
            if not file.is_file():
                continue
            # Serve each file according to its data type
            match file.suffix:
                case ".geojson" | ".shp" | ".geodb":
                    table_name = add_vector_file_to_db(conn, file)
                    gs.create_datastore_layer(workspace_name, data_store, table_name)
                case ".tif" | ".tiff" | ".geotiff":
                    gs.add_gtiff_to_geoserver(file, workspace_name, file.stem)
                case ".sld":
                    gs.add_style(file, replace=True)
    # If no models have been run we may still want to serve the non-static datasets, so create the stores.
    for workspace_name in non_statics:
        # These stores also should be initialised.
        gs.create_main_db_store(workspace_name)
    gs.create_graticules_layer(gs.Workspaces.STATIC_FILES_WORKSPACE)
