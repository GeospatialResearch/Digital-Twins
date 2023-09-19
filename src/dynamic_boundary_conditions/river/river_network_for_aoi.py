# -*- coding: utf-8 -*-
"""
This script processes REC1 data to construct a river network for the defined catchment area.
"""

import logging
from typing import Dict, Tuple

import numpy as np
import geopandas as gpd
from shapely.geometry import Point
from sqlalchemy.engine import Engine
import networkx as nx

from src.dynamic_boundary_conditions.river import main_river, river_data_to_from_db
from src.dynamic_boundary_conditions.river_network_to_from_db import (
    get_next_network_id,
    add_network_exclusions_to_db,
    store_rec1_network_to_db,
    get_existing_network_metadata_from_db,
    get_existing_network
)
from newzealidar.utils import get_dem_band_and_resolution_by_geometry

log = logging.getLogger(__name__)


def get_unique_nodes_dict(rec1_data_w_node_coords: gpd.GeoDataFrame) -> Dict[Point, int]:
    """
    Generates a dictionary that contains the unique node coordinates in the REC1 data for the catchment area.

    Parameters
    ----------
    rec1_data_w_node_coords : gpd.GeoDataFrame
        A GeoDataFrame containing the REC1 data for the catchment area with additional columns for the
        first and last coordinates of each LineString.

    Returns
    -------
    Dict[Point, int]
        A dictionary that contains the unique node coordinates (Point objects) in the REC1 data for the catchment area.
    """
    # Combine the first and last coordinates of each LineString into a single list
    rec1_node_coords = (
            rec1_data_w_node_coords["first_coord"].to_list() +
            rec1_data_w_node_coords["last_coord"].to_list()
    )
    # Extract unique node coordinates while preserving their original order
    unique_node_coords = [x for i, x in enumerate(rec1_node_coords) if x not in rec1_node_coords[:i]]
    # Create a dictionary containing the unique node coordinates
    unique_nodes_dict = {coord_point: i + 1 for i, coord_point in enumerate(unique_node_coords)}
    return unique_nodes_dict


def add_nodes_to_rec1(rec1_data_with_sdc: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Add columns for the first and last coordinates/nodes of each LineString in the REC1 data within the catchment area.

    Parameters
    ----------
    rec1_data_with_sdc : gpd.GeoDataFrame
        A GeoDataFrame containing the REC1 data for the catchment area with an additional column that identifies
        the associated sea-draining catchment for each REC1 geometry.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the REC1 data for the catchment area with additional columns for the
        first and last coordinates/nodes of each LineString.
    """
    # Create a copy of the input GeoDataFrame to avoid modifying the original data
    rec1_data_w_nodes = rec1_data_with_sdc.copy()
    # Add the "first_coord" column with the first coordinate of each LineString
    rec1_data_w_nodes["first_coord"] = rec1_data_w_nodes["geometry"].apply(lambda g: Point(g.coords[0]))
    # Add the "last_coord" column with the last coordinate of each LineString
    rec1_data_w_nodes["last_coord"] = rec1_data_w_nodes["geometry"].apply(lambda g: Point(g.coords[-1]))
    # Generate a dictionary that contains the unique node coordinates in the REC1 data
    unique_nodes_dict = get_unique_nodes_dict(rec1_data_w_nodes)
    # Map the first coordinates of LineStrings to their corresponding node indices and assign to the "first_node" column
    rec1_data_w_nodes["first_node"] = rec1_data_w_nodes["first_coord"].apply(lambda x: unique_nodes_dict.get(x, None))
    # Map the last coordinates of LineStrings to their corresponding node indices and assign to the "last_node" column
    rec1_data_w_nodes["last_node"] = rec1_data_w_nodes["last_coord"].apply(lambda x: unique_nodes_dict.get(x, None))
    return rec1_data_w_nodes


def add_nodes_intersection_type(
        catchment_area: gpd.GeoDataFrame,
        rec1_data_with_nodes: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Calculate and add an 'intersection_type' column to the GeoDataFrame that contains REC1 data with node information.

    Parameters
    ----------
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    rec1_data_with_nodes : gpd.GeoDataFrame
        A GeoDataFrame containing the REC1 data for the catchment area with additional columns for the
        first and last coordinates/nodes of each LineString.

    Returns
    -------
    gpd.GeoDataFrame
        The input GeoDataFrame with the 'intersection_type' column added.
    """
    # Extract the catchment polygon from the GeoDataFrame
    catchment_polygon = catchment_area["geometry"][0]
    # Calculate if the first and last coordinates/nodes intersect with the catchment_area
    rec1_data_with_nodes['first_intersects'] = rec1_data_with_nodes['first_coord'].intersects(catchment_polygon)
    rec1_data_with_nodes['last_intersects'] = rec1_data_with_nodes['last_coord'].intersects(catchment_polygon)
    # Define conditions and corresponding values for 'intersection_type' column
    conditions = [
        (rec1_data_with_nodes['first_intersects'] & rec1_data_with_nodes['last_intersects']),
        (rec1_data_with_nodes['first_intersects']),
        (rec1_data_with_nodes['last_intersects'])
    ]
    values = ['both_nodes', 'first_node', 'last_node']
    # Create 'intersection_type' column based on conditions
    rec1_data_with_nodes['intersect_catchment'] = np.select(conditions, values, default=None)
    # Remove unnecessary column
    rec1_data_with_nodes = rec1_data_with_nodes.drop(columns=['first_intersects', 'last_intersects'])
    return rec1_data_with_nodes


def prepare_network_data_for_construction(
        catchment_area: gpd.GeoDataFrame,
        rec1_data_with_sdc: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Prepares the necessary data for constructing the river network for the catchment area using the REC1 data.

    Parameters
    ----------
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    rec1_data_with_sdc : gpd.GeoDataFrame
        A GeoDataFrame containing the REC1 data for the catchment area with an additional column that identifies
        the associated sea-draining catchment for each REC1 geometry.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the necessary data for constructing the river network for the catchment area.
    """
    # Add columns for the first and last coordinates/nodes of each LineString in the REC1 data
    rec1_data_with_nodes = add_nodes_to_rec1(rec1_data_with_sdc)
    # Calculate and add an 'intersection_type' column for the nodes
    prepared_network_data = add_nodes_intersection_type(catchment_area, rec1_data_with_nodes)
    # Group the data by sea-draining catchments (identified by 'catch_id')
    grouped_data = prepared_network_data.groupby("catch_id")
    # Determine the river segment in each sea-draining catchment with the largest area
    prepared_network_data['is_largest_area'] = grouped_data['areakm2'].transform(lambda x: x == x.max())
    return prepared_network_data


def add_nodes_to_network(rec1_network: nx.Graph, prepared_network_data: gpd.GeoDataFrame) -> None:
    """
    Add nodes to the REC1 river network along with their attributes.

    Parameters
    ----------
    rec1_network : nx.Graph
        The REC1 river network, a directed graph, to which nodes will be added.
    prepared_network_data : gpd.GeoDataFrame
        A GeoDataFrame containing the necessary data for constructing the river network for the catchment area.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Iterate over rows in the prepared network data
    for _, row_edge in prepared_network_data.iterrows():
        # Extract node and coordinate information
        first_node, first_coord = row_edge["first_node"], row_edge["first_coord"]
        last_node, last_coord = row_edge["last_node"], row_edge["last_coord"]
        # Add nodes to the river network along with their attributes
        rec1_network.add_node(first_node, geometry=first_coord)
        rec1_network.add_node(last_node, geometry=last_coord)


def add_initial_edges_to_network(rec1_network: nx.Graph, prepared_network_data: gpd.GeoDataFrame) -> None:
    """
    Add initial edges to the REC1 river network along with their attributes.

    Parameters
    ----------
    rec1_network : nx.Graph
        The REC1 river network, a directed graph, to which initial edges will be added.
    prepared_network_data : gpd.GeoDataFrame
        A GeoDataFrame containing the necessary data for constructing the river network for the catchment area.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Iterate through each edge in the prepared network data
    for _, current_edge in prepared_network_data.iterrows():
        # Extract the area of the current edge
        current_edge_area = current_edge["areakm2"]
        # Find connected edges based on the first node of the current edge
        connected_edges = prepared_network_data[prepared_network_data["last_node"] == current_edge["first_node"]]

        # Check if there are any connected edges
        if not connected_edges.empty:
            # Iterate through connected edges to establish initial connections
            for _, connected_edge in connected_edges.iterrows():
                # Extract the area of the connected edge
                connected_edge_area = connected_edge["areakm2"]

                # Determine the direction of edge connection based on their areas
                if current_edge_area < connected_edge_area:
                    # Assign from and to nodes for the current edge and the connected edge
                    current_from_node, current_to_node = current_edge[["last_node", "first_node"]]
                    connected_from_node, connected_to_node = connected_edge[["last_node", "first_node"]]
                else:
                    # Assign from and to nodes for the current edge and the connected edge (reversed order)
                    connected_from_node, connected_to_node = connected_edge[["first_node", "last_node"]]
                    current_from_node, current_to_node = current_edge[["first_node", "last_node"]]

                # Create a list of tuples containing edges to be added
                edges = [
                    (current_from_node, current_to_node, current_edge),
                    (connected_from_node, connected_to_node, connected_edge)
                ]

                # Add the edges to the river network along with their attributes
                for from_node, to_node, edge_attributes in edges:
                    rec1_network.add_edge(
                        from_node,
                        to_node,
                        objectid=edge_attributes["objectid"],
                        nzreach=edge_attributes["nzreach"],
                        strm_order=edge_attributes["strm_order"],
                        areakm2=edge_attributes["areakm2"],
                        is_largest_area=edge_attributes["is_largest_area"],
                        catch_id=edge_attributes["catch_id"],
                        geometry=edge_attributes["geometry"]
                    )


def identify_absent_edges_to_add(rec1_network: nx.Graph, prepared_network_data: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Identify edges that are absent from the REC1 river network and require addition.

    Parameters
    ----------
    rec1_network : nx.Graph
        The REC1 river network, a directed graph.
    prepared_network_data : gpd.GeoDataFrame
        A GeoDataFrame containing the necessary data for constructing the river network for the catchment area.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing edges that are absent from the REC1 river network and require addition.
    """
    # Find the maximum value of "first_node" in the prepared network data
    max_first_node = prepared_network_data["first_node"].max()
    # Filter the prepared network data to include only edges where "last_node" is greater than the maximum "first_node"
    filtered_data = prepared_network_data[prepared_network_data["last_node"] > max_first_node]
    # Check for existing edges in the river network using the filtered data
    edge_exists = filtered_data.apply(
        lambda row:
        rec1_network.has_edge(row["first_node"], row["last_node"]) or
        rec1_network.has_edge(row["last_node"], row["first_node"]),
        axis=1
    )
    # Select edges that are absent in the REC1 river network
    absent_edges = filtered_data[~edge_exists].reset_index(drop=True)
    # Filter edges that have both the largest catchment area and intersect the catchment_area
    absent_edges_to_add = absent_edges[absent_edges["is_largest_area"]]
    absent_edges_to_add = absent_edges_to_add[~absent_edges_to_add['intersect_catchment'].isna()]
    return absent_edges_to_add


def add_absent_edges_to_network(
        engine: Engine,
        catchment_area: gpd.GeoDataFrame,
        rec1_network: nx.Graph,
        prepared_network_data: gpd.GeoDataFrame) -> None:
    """
    Add absent edges that are required for the current river network construction to the REC1 river network along with
    their attributes.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : GeoDataFrame
        A GeoDataFrame representing the catchment area.
    rec1_network : nx.Graph
        The REC1 river network, a directed graph, to which absent edges will be added.
    prepared_network_data : gpd.GeoDataFrame
        A GeoDataFrame containing the necessary data for constructing the river network for the catchment area.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Identify edges that are absent from the REC1 river network and require addition
    absent_edges_to_add = identify_absent_edges_to_add(rec1_network, prepared_network_data)

    # Determine the direction of absent edges
    if not absent_edges_to_add.empty:
        # Obtain the hydro DEM and its spatial extent
        hydro_dem, _ = get_dem_band_and_resolution_by_geometry(engine, catchment_area)
        hydro_dem_extent = main_river.get_extent_of_hydro_dem(engine, catchment_area)

        # Iterate through the selected intersection edges
        for _, absent_edge in absent_edges_to_add.iterrows():
            # Get how the nodes of each edge intersect with the catchment area
            intersect_catchment = absent_edge['intersect_catchment']

            if intersect_catchment == "both_nodes":
                # When both nodes of the edge intersect the catchment area
                # Use the coordinates of both nodes as the edge's start and end points
                first_coord, last_coord = absent_edge["first_coord"], absent_edge["last_coord"]
            elif intersect_catchment == "first_node":
                # When only the first node of the edge intersects with the catchment area
                # Use the boundary point on the Hydro DEM extent as the edge's end point
                boundary_point = hydro_dem_extent.intersection(absent_edge['geometry'])
                first_coord, last_coord = absent_edge["first_coord"], boundary_point
            else:
                # When only the last node of the edge intersects with the catchment area
                # Use the boundary point on the Hydro DEM extent as the edge's start point
                boundary_point = hydro_dem_extent.intersection(absent_edge['geometry'])
                first_coord, last_coord = boundary_point, absent_edge["last_coord"]

            # Retrieve elevation values for the edge's start and end points from the hydro DEM
            first_coord_z_val = hydro_dem.sel(x=first_coord.x, y=first_coord.y, method="nearest")['z'].values.item()
            last_coord_z_val = hydro_dem.sel(x=last_coord.x, y=last_coord.y, method="nearest")['z'].values.item()

            # Determine the direction of the edge based on elevation values
            if first_coord_z_val > last_coord_z_val:
                from_node, to_node = absent_edge["first_node"], absent_edge["last_node"]
            else:
                from_node, to_node = absent_edge["last_node"], absent_edge["first_node"]

            # Add the edge to the REC1 network with its attributes
            rec1_network.add_edge(
                from_node,
                to_node,
                objectid=absent_edge["objectid"],
                nzreach=absent_edge["nzreach"],
                strm_order=absent_edge["strm_order"],
                areakm2=absent_edge["areakm2"],
                is_largest_area=absent_edge["is_largest_area"],
                catch_id=absent_edge["catch_id"],
                geometry=absent_edge["geometry"]
            )


def add_edge_directions_to_network_data(
        engine: Engine,
        rec1_network_id: int,
        rec1_network: nx.Graph,
        prepared_network_data: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Add edge directions to the river network data based on the provided REC1 river network.
    Subsequently, eliminate REC1 geometries from the network data where the edge direction is absent (None), and
    append these excluded REC1 geometries to the relevant database table.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    rec1_network_id : int
        An identifier for the river network associated with the current run.
    rec1_network : nx.Graph
        The REC1 river network, a directed graph, used to determine the edge directions.
    prepared_network_data : gpd.GeoDataFrame
        A GeoDataFrame containing the necessary data for constructing the river network for the catchment area.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the updated river network data with added edge directions.
    """
    # Create a copy of the prepared network data to avoid modifying the original data
    network_data = prepared_network_data.copy()
    # Initialize an empty list to store edge directions
    directions = []
    # Iterate over rows in the network data
    for _, row in network_data.iterrows():
        # Check if there's an edge from first_node to last_node in REC1 network
        if rec1_network.has_edge(row["first_node"], row["last_node"]):
            # If there's an edge from first_node to last_node, the edge direction is 'to'
            directions.append("to")
        # Check if there's an edge from last_node to first_node in REC1 network
        elif rec1_network.has_edge(row["last_node"], row["first_node"]):
            # If there's an edge from last_node to first_node, the edge direction is 'from'
            directions.append("from")
        else:
            # If no edge exists in either direction, the edge direction is None
            directions.append(None)
    # Add the computed edge directions to the network data as a new column
    network_data["node_direction"] = directions
    # Remove rows from the network data where the edge direction is None
    rec1_network_data = network_data[~network_data["node_direction"].isna()].reset_index(drop=True)
    # Identify edges that were not added to the network
    rec1_network_exclusions = network_data[network_data["node_direction"].isna()].reset_index(drop=True)
    # Add excluded REC1 geometries in the River Network to the relevant database table
    add_network_exclusions_to_db(engine, rec1_network_id, rec1_network_exclusions,
                                 exclusion_cause="unable to determine edge direction")
    # Return the updated network data with added edge directions
    return rec1_network_data


def remove_unconnected_edges_from_network(
        engine: Engine,
        rec1_network_id: int,
        rec1_network: nx.Graph,
        rec1_network_data: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Remove REC1 river network edges that are not connected to their respective sea-draining catchment's end nodes.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    rec1_network_id : int
        An identifier for the river network associated with the current run.
    rec1_network : nx.Graph
        The REC1 river network, a directed graph, used to identify edges that are connected to the end nodes of their
        respective sea-draining catchments.
    rec1_network_data : gpd.GeoDataFrame
        A GeoDataFrame containing the REC1 river network data with added edge directions.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the modified river network data with REC1 geometries removed if they are not
        connected to their end nodes within their respective sea-draining catchments.
    """
    # Group the data by sea-draining catchment ID
    grouped_data = rec1_network_data.groupby("catch_id")
    # Initialize an empty list to keep track of REC1 geometries that need to be removed
    rec1_edges_to_remove = []
    # Iterate through each sea-draining catchment's network data
    for _, data in grouped_data:
        # Find the edge with the largest area within the current catchment
        largest_edge = data[data["is_largest_area"]].squeeze()
        # Determine the end node of the current catchment based on its direction
        catch_end_node = (
            largest_edge["last_node"] if largest_edge["node_direction"] == "to" else largest_edge["first_node"]
        )
        # Iterate through the edges within the current catchment
        for _, edge in data.iterrows():
            # Determine the starting node of the current edge based on its direction
            edge_start_node = edge["first_node"] if edge["node_direction"] == "to" else edge["last_node"]
            # Check if there is a path from the edge's start node to the catchment's end node
            if not nx.has_path(rec1_network, edge_start_node, catch_end_node):
                # If there isn't a path, remove the edge from the REC1 network
                rec1_network.remove_edge(edge["first_node"], edge["last_node"])
                # Add the edge's object ID to the list of edges to be removed
                rec1_edges_to_remove.append(edge["objectid"])
    # Filter to remove REC1 geometries that were excluded
    rec1_network_data_update = (
        rec1_network_data[~rec1_network_data["objectid"].isin(rec1_edges_to_remove)].reset_index(drop=True)
    )
    # Create a GeoDataFrame containing the edges that were removed from the REC1 network
    rec1_network_exclusions = (
        rec1_network_data[rec1_network_data["objectid"].isin(rec1_edges_to_remove)].reset_index(drop=True)
    )
    # Add excluded REC1 geometries in the River Network to the relevant database table
    add_network_exclusions_to_db(engine, rec1_network_id, rec1_network_exclusions,
                                 exclusion_cause="unconnected to its respective sea-draining catchment end node")
    return rec1_network_data_update


def build_rec1_river_network(
        engine: Engine,
        catchment_area: gpd.GeoDataFrame,
        rec1_network_id: int) -> Tuple[nx.DiGraph, gpd.GeoDataFrame]:
    """
    Builds a river network for the catchment area using the REC1 data.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    rec1_network_id : int
        An identifier for the river network associated with the current run.

    Returns
    -------
    Tuple[nx.DiGraph, gpd.GeoDataFrame]
        A tuple containing the constructed REC1 river network, represented as a directed graph (DiGraph),
        along with its associated data in the form of a GeoDataFrame.
    """
    # Get REC1 data from the database for the catchment area
    rec1_data_with_sdc = river_data_to_from_db.get_rec1_data_with_sdc_from_db(engine, catchment_area, rec1_network_id)
    # Prepare network data for construction
    prepared_network_data = prepare_network_data_for_construction(catchment_area, rec1_data_with_sdc)
    # Initialize an empty directed graph to represent the REC1 river network
    rec1_network = nx.DiGraph()
    # Add nodes to the REC1 river network
    add_nodes_to_network(rec1_network, prepared_network_data)
    # Connect nodes in the REC1 river network with initial edges
    add_initial_edges_to_network(rec1_network, prepared_network_data)
    # Complete the network by adding necessary remaining edges
    add_absent_edges_to_network(engine, catchment_area, rec1_network, prepared_network_data)
    # Integrate edge directions into the network data based on the REC1 river network structure
    network_data = add_edge_directions_to_network_data(engine, rec1_network_id, rec1_network, prepared_network_data)
    # Identify and remove unconnected edges from the network
    rec1_network_data = remove_unconnected_edges_from_network(engine, rec1_network_id, rec1_network, network_data)
    # Identify nodes with neither incoming nor outgoing edges and remove them from the network
    isolated_nodes = [node for node in rec1_network.nodes() if not rec1_network.degree(node)]
    rec1_network.remove_nodes_from(isolated_nodes)
    # Return the constructed REC1 river network and its associated data
    return rec1_network, rec1_network_data


def get_rec1_river_network(engine: Engine, catchment_area: gpd.GeoDataFrame) -> Tuple[nx.Graph, gpd.GeoDataFrame]:
    """
    Retrieve or create REC1 river network for the specified catchment area.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.

    Returns
    -------
    Tuple[nx.Graph, gpd.GeoDataFrame]
        A tuple containing the REC1 river network as a directed graph (DiGraph) and its associated data
        as a GeoDataFrame.
    """
    # Obtain the identifier for the REC1 river network associated with each run
    rec1_network_id = get_next_network_id(engine)
    # Retrieve existing REC1 river network metadata for the specified catchment area from the database
    existing_network_meta = get_existing_network_metadata_from_db(engine, catchment_area)

    if existing_network_meta.empty:
        # If no existing REC1 river network metadata is found, build the REC1 river network
        rec1_network, rec1_network_data = build_rec1_river_network(engine, catchment_area, rec1_network_id)
        # Store the newly created REC1 river network in the database
        store_rec1_network_to_db(engine, catchment_area, rec1_network_id, rec1_network, rec1_network_data)
    else:
        # If existing REC1 river network metadata is found, retrieve the network and its associated data
        rec1_network, rec1_network_data = get_existing_network(engine, existing_network_meta)
    return rec1_network, rec1_network_data


def get_rec1_boundary_points_on_bbox(
        catchment_area: gpd.GeoDataFrame,
        rec1_network_data: gpd.GeoDataFrame,
        rec1_network: nx.Graph) -> gpd.GeoDataFrame:
    """
    Get the boundary points where the REC1 rivers intersect with the catchment area boundary.

    Parameters
    -----------
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    rec1_network_data : gpd.GeoDataFrame
        A GeoDataFrame containing the REC1 network data.
    rec1_network : nx.Graph
        The REC1 river network, a directed graph.

    Returns
    --------
    gpd.GeoDataFrame
        A GeoDataFrame containing the boundary points where the REC1 rivers intersect with the catchment area boundary.
    """
    # Get the exterior boundary of the catchment area
    catchment_boundary = catchment_area.exterior.iloc[0]
    # Filter REC1 network data to obtain only the features intersecting with the catchment area boundary
    rec1_on_bbox = rec1_network_data[rec1_network_data.intersects(catchment_boundary)].reset_index(drop=True)
    # Initialize an empty list to store REC1 boundary points
    rec1_bound_points = []
    # Iterate over each row in the 'rec1_on_bbox' GeoDataFrame
    for _, row in rec1_on_bbox.iterrows():
        # Get the geometry for the current row
        geometry = row["geometry"]
        # Find the intersection between the catchment area boundary and REC1 geometry
        boundary_point = catchment_boundary.intersection(geometry)
        # Append the boundary point to the list
        rec1_bound_points.append(boundary_point)
    # Create a new column to store REC1 boundary points
    rec1_on_bbox["rec1_boundary_point"] = gpd.GeoSeries(rec1_bound_points, crs=rec1_on_bbox.crs)
    # Set the geometry of the GeoDataFrame to REC1 boundary point centroids
    rec1_bound_points_on_bbox = rec1_on_bbox.set_geometry("rec1_boundary_point")
    # Rename the 'geometry' column to 'rec1_river_line' for better clarity
    rec1_bound_points_on_bbox.rename(columns={'geometry': 'rec1_river_line'}, inplace=True)
    # rec1_bound_points_on_bbox = rec1_bound_points_on_bbox.drop(index=6) # what to do for this scenario (removed id 230484)??

    node_dict = {}
    for _, row in rec1_bound_points_on_bbox.iterrows():
        if row['node_direction'] == 'to':
            node_dict[row['objectid']] = row['first_node']
        else:
            node_dict[row['objectid']] = row['last_node']

    nodes_to_remove = []
    for object_id, node_number in node_dict.items():
        descendants = nx.descendants(rec1_network, node_number)
        downstream_nodes = [descendant for descendant in descendants if descendant in node_dict.values()]
        if downstream_nodes:
            nodes_to_remove.append(object_id)

    for object_id in nodes_to_remove:
        node_dict.pop(object_id)

    # Return the filtered GeoDataFrame based on remaining node_dict keys
    rec1_bound_points_on_bbox = rec1_bound_points_on_bbox[rec1_bound_points_on_bbox['objectid'].isin(node_dict.keys())]

    return rec1_bound_points_on_bbox


def get_rec1_network_data_on_bbox(
        catchment_area: gpd.GeoDataFrame,
        rec1_network_data: gpd.GeoDataFrame,
        rec1_network: nx.Graph) -> gpd.GeoDataFrame:
    """
    Get the REC1 network data that intersects with the catchment area boundary and identifies the corresponding points
    of intersection on the boundary.

    Parameters
    -----------
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    rec1_network_data : gpd.GeoDataFrame
        A GeoDataFrame containing the REC1 network data.
    rec1_network : nx.Graph
        The REC1 river network, a directed graph.

    Returns
    --------
    gpd.GeoDataFrame
        A GeoDataFrame containing the REC1 network data that intersects with the catchment area boundary,
        along with the corresponding points of intersection on the boundary.
    """
    # Get the line segments representing the catchment area boundary
    catchment_boundary_lines = main_river.get_catchment_boundary_lines(catchment_area)
    # Get the boundary points where the REC1 rivers intersect with the catchment area boundary
    rec1_bound_points = get_rec1_boundary_points_on_bbox(catchment_area, rec1_network_data, rec1_network)
    # Perform a spatial join between the REC1 boundary points and catchment boundary lines
    rec1_network_data_on_bbox = gpd.sjoin(
        rec1_bound_points, catchment_boundary_lines, how='left', predicate='intersects')
    # Remove unnecessary column
    rec1_network_data_on_bbox.drop(columns=['index_right'], inplace=True)
    # Merge the catchment boundary lines with the REC1 network data based on boundary line number
    rec1_network_data_on_bbox = rec1_network_data_on_bbox.merge(
        catchment_boundary_lines, on='boundary_line_no', how='left').sort_index()
    # Rename the geometry column to 'boundary_line' for better clarity
    rec1_network_data_on_bbox.rename(columns={'geometry': 'boundary_line'}, inplace=True)
    return rec1_network_data_on_bbox
