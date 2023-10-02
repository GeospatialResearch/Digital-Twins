# -*- coding: utf-8 -*-
"""
@Description: Store both the REC1 river network and its associated data in files, and their metadata in the database.
              Retrieve the existing REC1 river network and its associated data.
              Manages the addition of REC1 geometries that have been excluded from the river network in the database and
              retrieves them from the database for an existing REC1 river network.
@Author: sli229
"""

import pathlib
import logging
from typing import Tuple
from datetime import datetime
import pickle

import geopandas as gpd
import numpy as np
import shapely.wkt
from sqlalchemy import select, func
from sqlalchemy.engine import Engine
import networkx as nx

from src.config import get_env_variable
from src.digitaltwin.tables import (
    check_table_exists,
    create_table,
    execute_query,
    RiverNetworkExclusions,
    RiverNetworkOutput
)

log = logging.getLogger(__name__)


def get_next_network_id(engine: Engine) -> int:
    """
    Get the next available REC1 River Network ID from the River Network Exclusions table.

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
    query = select([func.coalesce(func.max(RiverNetworkExclusions.rec1_network_id), 0) + 1])
    # Execute the query
    with engine.connect() as connection:
        rec1_network_id = connection.execute(query).scalar()
    return rec1_network_id


def add_network_exclusions_to_db(
        engine: Engine,
        rec1_network_id: int,
        rec1_network_exclusions: gpd.GeoDataFrame,
        exclusion_cause: str) -> None:
    """
    Add REC1 geometries that are excluded from the river network for the current run in the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    rec1_network_id : int
        An identifier for the river network associated with the current run.
    rec1_network_exclusions : gpd.GeoDataFrame
        A GeoDataFrame containing the REC1 geometries that are excluded from the river network for the current run.
    exclusion_cause : str
        Cause of exclusion, i.e., the reason why the REC1 river geometry was excluded.

    Returns
    -------
    None
        This function does not return any value.
    """
    if not rec1_network_exclusions.empty:
        # Assign the exclusion cause to the 'exclusion_cause' column
        rec1_network_exclusions["exclusion_cause"] = exclusion_cause
        # Select the necessary columns and reset the index
        rec1_network_exclusions = (
            rec1_network_exclusions[["objectid", "exclusion_cause", "geometry"]].reset_index(drop=True))
        # Insert 'rec1_network_id' to associate it with the river network of the current run
        rec1_network_exclusions.insert(0, "rec1_network_id", rec1_network_id)
        # Record excluded REC1 geometries in the relevant table in the database
        rec1_network_exclusions.to_postgis(RiverNetworkExclusions.__tablename__, engine, if_exists="append")
        # Convert the excluded REC1 river segment object IDs to a list
        excluded_ids = rec1_network_exclusions["objectid"].tolist()
        # Log a warning message indicating the reason and IDs of the excluded REC1 river segments
        log.warning(f"Excluded REC1 from river network because '{exclusion_cause}': "
                    f"{', '.join(map(str, excluded_ids))}")


def get_new_network_output_paths() -> Tuple[pathlib.Path, pathlib.Path]:
    """
    Get new file paths that incorporate the current timestamp into the filenames for storing both the REC1 Network and
    its associated data.

    Returns
    -------
    Tuple[pathlib.Path, pathlib.Path]
        A tuple containing the file path to the REC1 Network and the file path to the REC1 Network data.
    """
    # Get the current timestamp in "YYYY_MM_DD_HH_MM_SS" format
    dt_string = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    # Get the data directory from the environment variable
    data_dir = get_env_variable("DATA_DIR", cast_to=pathlib.Path)
    # Define the directory for storing the REC1 Network and its associated data
    network_dir = data_dir / "rec1_network" / dt_string
    # Create the REC1 Network directory if it does not already exist
    network_dir.mkdir(parents=True, exist_ok=True)
    # Create the file path for the REC1 Network with the current timestamp
    network_path = (network_dir / f"{dt_string}_network.pickle")
    # Create the file path for the REC1 Network data with the current timestamp
    network_data_path = (network_dir / f"{dt_string}_network_data.geojson")
    return network_path, network_data_path


def get_network_output_metadata(
        network_path: pathlib.Path,
        network_data_path: pathlib.Path,
        catchment_area: gpd.GeoDataFrame) -> Tuple[str, str, str]:
    """
    Get metadata associated with the REC1 Network.

    Parameters
    ----------
    network_path : pathlib.Path
        The path to the REC1 Network file.
    network_data_path : pathlib.Path
        The path to the REC1 Network data file.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.

    Returns
    -------
    Tuple[str, str, str]
        A tuple containing the absolute path to the REC1 Network file as a string, the absolute path to the REC1 Network
        data file as a string, and the Well-Known Text (WKT) representation of the catchment area's geometry.
    """
    # Get the absolute path of the REC1 Network file as a string
    network_path = network_path.as_posix()
    # Get the absolute path of the REC1 Network data file as a string
    network_data_path = network_data_path.as_posix()
    # Get the WKT representation of the catchment area's geometry
    catchment_geom = catchment_area["geometry"].to_wkt().iloc[0]
    # Return the metadata as a tuple
    return network_path, network_data_path, catchment_geom


def store_rec1_network_to_db(
        engine: Engine,
        catchment_area: gpd.GeoDataFrame,
        rec1_network_id: int,
        rec1_network: nx.Graph,
        rec1_network_data: gpd.GeoDataFrame) -> None:
    """
    Store both the REC1 river network and its associated data in files, and their metadata in the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    rec1_network_id : int
        An identifier for the river network associated with the current run.
    rec1_network : nx.Graph
        The constructed REC1 river network, represented as a directed graph (DiGraph).
    rec1_network_data : gpd.GeoDataFrame
        A GeoDataFrame containing the REC1 river network data.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Get new file paths for storing both the REC1 Network and its associated data
    network_path, network_data_path = get_new_network_output_paths()
    # Save the REC1 river network to the specified file
    with open(network_path, "wb") as file:
        pickle.dump(rec1_network, file)

    # Convert the 'first_coord' and 'last_coord' columns to string format to facilitate exporting
    network_data = rec1_network_data.copy()
    network_data["first_coord"] = network_data["first_coord"].astype(str)
    network_data["last_coord"] = network_data["last_coord"].astype(str)
    # Save the REC1 river network data to the specified file
    network_data.to_file(str(network_data_path), driver="GeoJSON")

    # Create the REC1 Network Output table in the database if it doesn't exist
    create_table(engine, RiverNetworkOutput)
    # Get metadata related to the REC1 Network Output
    network_path, network_data_path, geometry = get_network_output_metadata(
        network_path, network_data_path, catchment_area)
    # Create a new query object representing the REC1 Network Output metadata
    query = RiverNetworkOutput(
        rec1_network_id=rec1_network_id,
        network_path=network_path,
        network_data_path=network_data_path,
        geometry=geometry)
    # Execute the query to store the REC1 Network Output metadata in the database
    execute_query(engine, query)
    # Log a message indicating the successful storage of REC1 network output metadata in the database
    log.info("REC1 river network metadata successfully stored in the database.")


def get_existing_network_metadata_from_db(engine: Engine, catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Retrieve existing REC1 river network metadata for the specified catchment area from the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the existing REC1 river network metadata for the specified catchment area.
    """
    # Create the REC1 Network Output table in the database if it doesn't exist
    create_table(engine, RiverNetworkOutput)
    # Extract the catchment polygon from the catchment area and convert it to Well-Known Text (WKT) format
    catchment_polygon = catchment_area["geometry"].iloc[0]
    catchment_polygon_wkt = shapely.wkt.dumps(catchment_polygon, rounding_precision=6)
    # Query the REC1 Network Output table to find existing REC1 river network metadata for the catchment area
    query = f"""
    SELECT *
    FROM rec1_network_output
    WHERE ST_Contains(geometry, ST_GeomFromText('{catchment_polygon_wkt}', 2193));
    """
    # Fetch the query result as a GeoPandas DataFrame
    existing_network_meta = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry")
    return existing_network_meta


def get_existing_network(engine: Engine, existing_network_meta: gpd.GeoDataFrame) -> Tuple[nx.Graph, gpd.GeoDataFrame]:
    """
    Retrieve existing REC1 river network and its associated data.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    existing_network_meta : gpd.GeoDataFrame
        A GeoDataFrame containing the metadata for the existing REC1 river network.

    Returns
    -------
    Tuple[nx.Graph, gpd.GeoDataFrame]
        A tuple containing the existing REC1 river network as a directed graph (DiGraph) and its associated data
        as a GeoDataFrame.
    """
    # Extract metadata for the existing REC1 river network
    existing_network_series = existing_network_meta.iloc[0]
    # Extract the REC1 river network ID from the provided metadata
    rec1_network_id = existing_network_series["rec1_network_id"]
    # Construct a query to retrieve exclusion data for the existing REC1 river network
    query = f"""
    SELECT *
    FROM rec1_network_exclusions
    WHERE rec1_network_id = {rec1_network_id};
    """
    # Query the database to retrieve exclusion data for the existing REC1 river network
    rec1_network_exclusions = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry")
    # Group exclusion data by the cause of exclusion
    grouped_data = rec1_network_exclusions.groupby("exclusion_cause")
    # Iterate through grouped exclusion data, where each group represents a cause of exclusion
    for exclusion_cause, data in grouped_data:
        # Convert the excluded REC1 river segment object IDs to a list
        excluded_ids = data["objectid"].tolist()
        # Log a warning message indicating the reason and IDs of the excluded REC1 river segments
        log.warning(f"Excluded REC1 from river network because '{exclusion_cause}': "
                    f"{', '.join(map(str, excluded_ids))}")
    # Load the REC1 river network graph
    with open(existing_network_series["network_path"], "rb") as file:
        rec1_network = pickle.load(file)
    # Load the REC1 river network data containing geometry information
    rec1_network_data = gpd.read_file(existing_network_series["network_data_path"])
    # Set the data type of the 'first_coord' and 'last_coord' columns to geometry
    rec1_network_data["first_coord"] = rec1_network_data["first_coord"].apply(shapely.wkt.loads).astype("geometry")
    rec1_network_data["last_coord"] = rec1_network_data["last_coord"].apply(shapely.wkt.loads).astype("geometry")
    # Replace NaN values with None in the 'node_intersect_aoi' column
    rec1_network_data["node_intersect_aoi"] = rec1_network_data["node_intersect_aoi"].replace(np.nan, None)
    return rec1_network, rec1_network_data