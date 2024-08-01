# -*- coding: utf-8 -*-
"""
This script handles the following tasks: storing both the REC river network and its associated data in files along with
their metadata in the database, retrieving the existing REC river network and its associated data from the database,
and managing the addition of REC geometries that have been excluded from the river network in the database,
as well as retrieving them for an existing REC river network.
"""  # noqa: D400

import logging
import pathlib
import pickle
from datetime import datetime
from typing import Tuple, NamedTuple

import geopandas as gpd
import networkx as nx
import numpy as np
import shapely.wkt
from sqlalchemy import select, func
from sqlalchemy.engine import Engine

from src.config import EnvVariable
from src.digitaltwin.s3_connection import S3Manager
from src.digitaltwin.tables import (
    check_table_exists,
    create_table,
    execute_query,
    RiverNetworkExclusions,
    RiverNetwork
)

log = logging.getLogger(__name__)


class NetworkMetadata(NamedTuple):
    """
    Represents metadata associated with the REC Network.

    Attributes
    ----------
    network_path : str
        The path to the REC Network file.
    network_data_path : str
        The path to the REC Network data file.
    catchment_geom : str
        The Well-Known Text (WKT) representation of the catchment area's geometry.
    """
    network_path: str
    network_data_path: str
    catchment_geom: str


def get_next_network_id(engine: Engine) -> int:
    """
    Get the next available REC River Network ID from the River Network Exclusions table.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.

    Returns
    -------
    int
        An identifier for the river network associated with each run, representing the next available River Network ID.
    """
    # Check if the River Network Exclusions table exists; if not, create it
    if not check_table_exists(engine, RiverNetworkExclusions.__tablename__):
        create_table(engine, RiverNetworkExclusions)
    # Build a query to find the next available river network ID
    query = select([func.coalesce(func.max(RiverNetworkExclusions.rec_network_id), 0) + 1])
    # Execute the query
    with engine.connect() as connection:
        rec_network_id = connection.execute(query).scalar()
    return rec_network_id


def add_network_exclusions_to_db(
        engine: Engine,
        rec_network_id: int,
        rec_network_exclusions: gpd.GeoDataFrame,
        exclusion_cause: str) -> None:
    """
    Add REC geometries that are excluded from the river network for the current run in the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    rec_network_id : int
        An identifier for the river network associated with the current run.
    rec_network_exclusions : gpd.GeoDataFrame
        A GeoDataFrame containing the REC geometries that are excluded from the river network for the current run.
    exclusion_cause : str
        Cause of exclusion, i.e., the reason why the REC river geometry was excluded.
    """
    if not rec_network_exclusions.empty:
        # Assign the exclusion cause to the 'exclusion_cause' column
        rec_network_exclusions["exclusion_cause"] = exclusion_cause
        # Select the necessary columns and reset the index
        rec_network_exclusions = (
            rec_network_exclusions[["objectid", "exclusion_cause", "geometry"]].reset_index(drop=True))
        # Insert 'rec_network_id' to associate it with the river network of the current run
        rec_network_exclusions.insert(0, "rec_network_id", rec_network_id)
        # Record excluded REC geometries in the relevant table in the database
        rec_network_exclusions.to_postgis(RiverNetworkExclusions.__tablename__, engine, if_exists="append")
        # Convert the excluded REC river segment object IDs to a list
        excluded_ids = rec_network_exclusions["objectid"].tolist()
        # Log a warning message indicating the reason and IDs of the excluded REC river segments
        log.warning(f"Excluded REC from river network because '{exclusion_cause}': "
                    f"{', '.join(map(str, excluded_ids))}")


def get_new_network_output_paths() -> Tuple[pathlib.Path, pathlib.Path]:
    """
    Get new file paths that incorporate the current timestamp into the filenames for storing both the REC Network and
    its associated data.

    Returns
    -------
    Tuple[pathlib.Path, pathlib.Path]
        A tuple containing the file path to the REC Network and the file path to the REC Network data.
    """  # noqa: D400
    # Retrieve the value of the environment variable "USE_AWS_S3_BUCKET"
    use_aws_s3_bucket = config.get_env_variable("USE_AWS_S3_BUCKET", cast_to=bool)
    # Get the current timestamp in "YYYY_MM_DD_HH_MM_SS" format
    dt_string = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    # Get the data directory from the environment variable
    data_dir = EnvVariable.DATA_DIR
    # Define the directory for storing the REC Network and its associated data
    network_dir = data_dir / "rec_network" / dt_string
    # If not using S3, create the REC Network directory if it does not already exist
    if not use_aws_s3_bucket:
        network_dir.mkdir(parents=True, exist_ok=True)
    # Create the file path for the REC Network with the current timestamp
    network_path = network_dir / f"{dt_string}_network.pickle"
    # Create the file path for the REC Network data with the current timestamp
    network_data_path = network_dir / f"{dt_string}_network_data.geojson"
    return network_path, network_data_path


def get_network_output_metadata(catchment_area: gpd.GeoDataFrame) -> NetworkMetadata:
    """
    Get metadata associated with the REC Network.

    Parameters
    ----------
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.

    Returns
    -------
    NetworkMetadata
        A named tuple containing the path to the REC Network file, the path to the REC Network data file, and
        the Well-Known Text (WKT) representation of the catchment area's geometry.
    """
    # Generate timestamped file paths for REC river network and associated data storage
    network_path, network_data_path = get_new_network_output_paths()
    # Get the path of the REC Network file as a string
    network_path = network_path.as_posix()
    # Get the path of the REC Network data file as a string
    network_data_path = network_data_path.as_posix()
    # Get the WKT representation of the catchment area's geometry
    catchment_geom = catchment_area["geometry"].to_wkt().iloc[0]
    # Return the metadata associated with the REC Network output
    return NetworkMetadata(network_path, network_data_path, catchment_geom)


def store_rec_network_to_db(
        engine: Engine,
        catchment_area: gpd.GeoDataFrame,
        rec_network_id: int,
        rec_network: nx.DiGraph,
        rec_network_data: gpd.GeoDataFrame) -> None:
    """
    Store both the REC river network and its associated data in files, and their metadata in the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    rec_network_id : int
        An identifier for the river network associated with the current run.
    rec_network : nx.DiGraph
        The constructed REC river network, represented as a directed graph (DiGraph).
    rec_network_data : gpd.GeoDataFrame
        A GeoDataFrame containing the REC river network data.
    """
    log.info("Adding REC river network metadata to the database.")
    # Get metadata related to the REC Network Output
    network_path, network_data_path, geometry = get_network_output_metadata(catchment_area)

    # Convert the 'first_coord' and 'last_coord' columns to string format to facilitate exporting
    network_data = rec_network_data.copy()
    network_data["first_coord"] = network_data["first_coord"].astype(str)
    network_data["last_coord"] = network_data["last_coord"].astype(str)
    # Retrieve the value of the environment variable "USE_AWS_S3_BUCKET"
    use_aws_s3_bucket = config.get_env_variable("USE_AWS_S3_BUCKET", cast_to=bool)
    # If True, store REC river network and its associated data in S3 bucket
    if use_aws_s3_bucket:
        s3_manager = S3Manager()
        s3_manager.store_object(s3_object_key=network_path, data=rec_network)
        s3_manager.store_object(s3_object_key=network_data_path, data=network_data)
    # If False, store REC river network and its associated data locally
    else:
        # Save the REC river network to the specified file
        with open(network_path, "wb") as file:
            pickle.dump(rec_network, file)
        log.info(f"Saved the REC river network to {network_path}")
        # Save the REC river network data to the specified file
        network_data.to_file(network_data_path, driver="GeoJSON")
        log.info(f"Saved the REC river network data to {network_data_path}")

    # Create the REC Network table in the database if it doesn't exist
    create_table(engine, RiverNetwork)
    # Create a new query object representing the REC Network metadata
    query = RiverNetwork(
        rec_network_id=rec_network_id,
        network_path=network_path,
        network_data_path=network_data_path,
        geometry=geometry)
    # Execute the query to store the REC Network metadata in the database
    execute_query(engine, query)
    # Log a message indicating the successful storage of REC network metadata in the database
    log.info("Successfully added the REC river network metadata to the database.")


def get_existing_network_metadata_from_db(engine: Engine, catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Retrieve existing REC river network metadata for the specified catchment area from the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the existing REC river network metadata for the specified catchment area.
    """
    # Create the REC Network table in the database if it doesn't exist
    create_table(engine, RiverNetwork)
    # Extract the catchment polygon from the catchment area and convert it to Well-Known Text (WKT) format
    catchment_polygon = catchment_area["geometry"].iloc[0]
    catchment_polygon_wkt = shapely.wkt.dumps(catchment_polygon, rounding_precision=6)
    # Query the REC Network Output table to find existing REC river network metadata for the catchment area
    query = f"""
    SELECT *
    FROM {RiverNetwork.__tablename__}
    WHERE ST_Equals(geometry, ST_GeomFromText('{catchment_polygon_wkt}', 2193));
    """
    # Fetch the query result as a GeoPandas DataFrame
    existing_network_meta = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry")
    return existing_network_meta


def get_existing_network(engine: Engine, existing_network_meta: gpd.GeoDataFrame) -> Tuple[nx.Graph, gpd.GeoDataFrame]:
    """
    Retrieve existing REC river network and its associated data.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    existing_network_meta : gpd.GeoDataFrame
        A GeoDataFrame containing the metadata for the existing REC river network.

    Returns
    -------
    Tuple[nx.Graph, gpd.GeoDataFrame]
        A tuple containing the existing REC river network as a directed graph (DiGraph) and its associated data
        as a GeoDataFrame.
    """
    log.info("Retrieving the existing REC river network and its associated data "
             "for the requested catchment area from the database.")
    # Extract metadata for the existing REC river network
    existing_network_series = existing_network_meta.iloc[0]
    # Extract the REC river network ID from the provided metadata
    rec_network_id = existing_network_series["rec_network_id"]
    # Construct a query to retrieve exclusion data for the existing REC river network
    query = f"""
    SELECT *
    FROM {RiverNetworkExclusions.__tablename__}
    WHERE rec_network_id = {rec_network_id};
    """
    # Query the database to retrieve exclusion data for the existing REC river network
    rec_network_exclusions = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry")
    # Group exclusion data by the cause of exclusion
    grouped_data = rec_network_exclusions.groupby("exclusion_cause")
    # Iterate through grouped exclusion data, where each group represents a cause of exclusion
    for exclusion_cause, data in grouped_data:
        # Convert the excluded REC river segment object IDs to a list
        excluded_ids = data["objectid"].tolist()
        # Log a warning message indicating the reason and IDs of the excluded REC river segments
        log.warning(f"Excluded REC from river network because '{exclusion_cause}': "
                    f"{', '.join(map(str, excluded_ids))}")

    # Retrieve the value of the environment variable "USE_AWS_S3_BUCKET"
    use_aws_s3_bucket = config.get_env_variable("USE_AWS_S3_BUCKET", cast_to=bool)
    # If True, retrieve REC river network and its associated data from S3 bucket
    if use_aws_s3_bucket:
        s3_manager = S3Manager()
        rec_network = s3_manager.retrieve_object(s3_object_key=existing_network_series["network_path"])
        rec_network_data = s3_manager.retrieve_object(s3_object_key=existing_network_series["network_data_path"])
    # If False, retrieve REC river network and its associated data from local storage
    else:
        # Load the REC river network graph
        with open(existing_network_series["network_path"], "rb") as file:
            rec_network = pickle.load(file)
        # Load the REC river network data containing geometry information
        rec_network_data = gpd.read_file(existing_network_series["network_data_path"])
    # Set the data type of the 'first_coord' and 'last_coord' columns to geometry
    rec_network_data["first_coord"] = rec_network_data["first_coord"].apply(shapely.wkt.loads).astype("geometry")
    rec_network_data["last_coord"] = rec_network_data["last_coord"].apply(shapely.wkt.loads).astype("geometry")
    # Replace NaN values with None in the 'node_intersect_aoi' column
    rec_network_data["node_intersect_aoi"] = rec_network_data["node_intersect_aoi"].replace(np.nan, None)
    # Log a message indicating the successful retrieval of REC river network and its associated data from the database
    log.info("Successfully retrieved the existing REC river network and its associated data for the catchment area.")
    return rec_network, rec_network_data
