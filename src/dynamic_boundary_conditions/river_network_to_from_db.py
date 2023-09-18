# -*- coding: utf-8 -*-
"""
@Description: Store the metadata of the REC1 river network and its associated data in the database, and
              retrieve existing REC1 river network metadata for the specified catchment area.
@Author: sli229
"""

import pathlib
import logging
from typing import Tuple
from datetime import datetime
import pickle

import geopandas as gpd
import shapely.wkt
from sqlalchemy.engine import Engine
import networkx as nx

from src.config import get_env_variable
from src.digitaltwin.tables import create_table, execute_query, RiverNetworkOutput

log = logging.getLogger(__name__)


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
    # Get the directory for storing the REC1 Network and its associated data
    network_dir = get_env_variable("DATA_DIR_NETWORK", cast_to=pathlib.Path) / dt_string
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


def store_rec1_network_metadata_to_db(
        engine: Engine,
        catchment_area: gpd.GeoDataFrame,
        rec1_network_id: int,
        rec1_network: nx.Graph,
        rec1_network_data: gpd.GeoDataFrame) -> None:
    """
    Store the metadata of the REC1 river network and its associated data in the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    rec1_network_id : int
        An identifier for the river network associated with the current run.
    rec1_network : nx.Graph
        The constructed REC1 river network, represented as a directed graph (DiGraph)
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
    with open(network_path, 'wb') as file:
        pickle.dump(rec1_network, file)

    # Convert the 'first_coord' and 'last_coord' columns to string format to facilitate exporting
    rec1_network_data['first_coord'] = rec1_network_data['first_coord'].astype(str)
    rec1_network_data['last_coord'] = rec1_network_data['last_coord'].astype(str)
    # Save the REC1 river network data to the specified file
    rec1_network_data.to_file(str(network_data_path), driver="GeoJSON")

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


def get_existing_network_metadata(engine: Engine, catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Retrieve existing REC1 river network metadata for the specified catchment area.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing existing REC1 river network metadata for the specified catchment area.
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
    existing_network = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry")
    return existing_network
