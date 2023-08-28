# -*- coding: utf-8 -*-
"""
This script processes REC1 data to construct a river network for the defined catchment area.
Additionally, it identifies intersections between the REC1 rivers and the catchment area boundary,
providing valuable information for further use.
"""

from typing import Dict, Tuple, List

import geopandas as gpd
from shapely.geometry import Point
import networkx as nx

from src.dynamic_boundary_conditions.river import main_river


def add_first_and_last_coords_to_rec1(rec1_data: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Adds columns for the first and last coordinates of each LineString in the REC1 data for the catchment area.

    Parameters
    ----------
    rec1_data : gpd.GeoDataFrame
        A GeoDataFrame containing the REC1 data for the catchment area.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the REC1 data for the catchment area with additional columns for the
        first and last coordinates of each LineString.
    """
    # Create a copy of the input GeoDataFrame to avoid modifying the original data
    rec1_data_w_node_coords = rec1_data.copy()
    # Add the "first_coord" column with the first coordinate of each LineString
    rec1_data_w_node_coords["first_coord"] = rec1_data_w_node_coords["geometry"].apply(lambda g: Point(g.coords[0]))
    # Add the "last_coord" column with the last coordinate of each LineString
    rec1_data_w_node_coords["last_coord"] = rec1_data_w_node_coords["geometry"].apply(lambda g: Point(g.coords[-1]))
    return rec1_data_w_node_coords


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
    # Find unique node coordinates
    unique_node_coords = [x for i, x in enumerate(rec1_node_coords) if x not in rec1_node_coords[:i]]
    # Create a dictionary containing the unique node coordinates
    unique_nodes_dict = {coord_point: i + 1 for i, coord_point in enumerate(unique_node_coords)}
    return unique_nodes_dict


def prepare_network_data_for_construction(rec1_data: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Prepares the necessary data for constructing the river network for the catchment area using the REC1 data.

    Parameters
    ----------
    rec1_data : gpd.GeoDataFrame
        A GeoDataFrame containing the REC1 data for the catchment area.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the necessary data for constructing the river network for the catchment area.
    """
    # Add columns for the first and last coordinates of each LineString in the REC1 data
    prepared_network_data = add_first_and_last_coords_to_rec1(rec1_data)
    # Generate a dictionary that contains the unique node coordinates in the REC1 data
    unique_nodes_dict = get_unique_nodes_dict(prepared_network_data)
    # Map the first coordinates of LineStrings to their corresponding node indices and assign to the "first_node" column
    prepared_network_data["first_node"] = prepared_network_data["first_coord"].apply(
        lambda x: unique_nodes_dict.get(x, None))
    # Map the last coordinates of LineStrings to their corresponding node indices and assign to the "last_node" column
    prepared_network_data["last_node"] = prepared_network_data["last_coord"].apply(
        lambda x: unique_nodes_dict.get(x, None))
    return prepared_network_data


def add_nodes_to_network(prepared_network_data: gpd.GeoDataFrame, rec1_network: nx.Graph) -> None:
    """
    Add nodes to the REC1 river network along with their attributes.

    Parameters
    ----------
    prepared_network_data : gpd.GeoDataFrame
        A GeoDataFrame containing the necessary data for constructing the river network for the catchment area.
    rec1_network : nx.Graph
        The REC1 river network, a directed graph, to which nodes will be added.

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


def add_initial_edges_to_network(prepared_network_data: gpd.GeoDataFrame, rec1_network: nx.Graph) -> None:
    """
    Add initial edges to the REC1 river network along with their attributes.

    Parameters
    ----------
    prepared_network_data : gpd.GeoDataFrame
        A GeoDataFrame containing the necessary data for constructing the river network for the catchment area.
    rec1_network : nx.Graph
        The REC1 river network, a directed graph, to which initial edges will be added.

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
                        areakm2=edge_attributes["areakm2"],
                        strm_order=edge_attributes["strm_order"],
                        geometry=edge_attributes["geometry"]
                    )


def add_remaining_edges_to_network(prepared_network_data: gpd.GeoDataFrame, rec1_network: nx.Graph) -> None:
    """
    Add remaining edges to the REC1 river network along with their attributes.

    Parameters
    ----------
    prepared_network_data : gpd.GeoDataFrame
        A GeoDataFrame containing the necessary data for constructing the river network for the catchment area.
    rec1_network : nx.Graph
        The REC1 river network, a directed graph, to which remaining edges will be added.

    Returns
    -------
    None
        This function does not return any value.
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
    # Select edges that do not already exist in the river network
    edges_not_exist = filtered_data[~edge_exists]

    # If there are edges that do not exist in the network, process them
    if not edges_not_exist.empty:
        # Group the edges by the "last_node" to process them in groups
        grouped = edges_not_exist.groupby("last_node")
        # Iterate through each group of edges
        for _, group_data in grouped:
            # Sort the group data by "areakm2" in ascending order
            sorted_group_data = group_data.sort_values(by='areakm2').reset_index(drop=True)
            # Iterate through each edge in the sorted group
            for _, row_edge in sorted_group_data.iterrows():
                # Add the edge to the rec1_network along with its attributes
                rec1_network.add_edge(
                    row_edge["first_node"],
                    row_edge["last_node"],
                    objectid=row_edge["objectid"],
                    nzreach=row_edge["nzreach"],
                    areakm2=row_edge["areakm2"],
                    strm_order=row_edge["strm_order"],
                    geometry=row_edge["geometry"]
                )


def add_edge_directions_to_network_data(
        prepared_network_data: gpd.GeoDataFrame,
        rec1_network: nx.Graph) -> gpd.GeoDataFrame:
    """
    Add edge directions to the river network data based on the provided REC1 river network.

    Parameters
    ----------
    prepared_network_data : gpd.GeoDataFrame
        A GeoDataFrame containing the necessary data for constructing the river network for the catchment area.
    rec1_network : nx.Graph
        The REC1 river network, a directed graph, used to determine the edge directions.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the updated river network data with added edge directions.
    """
    # Create a copy of the prepared network data to avoid modifying the original data
    rec1_network_data = prepared_network_data.copy()
    # Initialize an empty list to store edge directions
    directions: List[str] = []
    # Iterate over rows in the network data
    for _, row in rec1_network_data.iterrows():
        # Check if there's an edge from first_node to last_node in REC1 network
        if rec1_network.has_edge(row["first_node"], row["last_node"]):
            # If there's an edge from first_node to last_node, the edge direction is 'to'
            directions.append("to")
        # Check if there's an edge from last_node to first_node in REC1 network
        elif rec1_network.has_edge(row["last_node"], row["first_node"]):
            # If there's an edge from last_node to first_node, the edge direction is 'from'
            directions.append("from")
        else:
            # If no edge exists in either direction, the edge direction is 'unknown'
            directions.append("unknown")
    # Add the computed edge directions to the network data as a new column
    rec1_network_data["node_direction"] = directions
    # Return the updated network data with added edge directions
    return rec1_network_data


def build_rec1_river_network(rec1_data: gpd.GeoDataFrame) -> Tuple[nx.DiGraph, gpd.GeoDataFrame]:
    """
    Builds a river network for the catchment area using the REC1 data.

    Parameters
    ----------
    rec1_data : gpd.GeoDataFrame
        A GeoDataFrame containing the REC1 data for the catchment area.

    Returns
    -------
    Tuple[nx.DiGraph, gpd.GeoDataFrame]
        A tuple containing the constructed REC1 river network, represented as a directed graph (DiGraph),
        along with its associated data in the form of a GeoDataFrame.
    """
    # Prepare network data for construction
    prepared_network_data = prepare_network_data_for_construction(rec1_data)
    # Initialize an empty directed graph to represent the REC1 river network
    rec1_network = nx.DiGraph()
    # Add nodes to the REC1 river network
    add_nodes_to_network(prepared_network_data, rec1_network)
    # Connect nodes in the REC1 river network with initial edges
    add_initial_edges_to_network(prepared_network_data, rec1_network)
    # Complete the network by adding necessary remaining edges
    add_remaining_edges_to_network(prepared_network_data, rec1_network)
    # Integrate edge directions into the network data based on the REC1 river network structure
    rec1_network_data = add_edge_directions_to_network_data(prepared_network_data, rec1_network)
    # Return the constructed REC1 river network and its associated data
    return rec1_network, rec1_network_data


def get_rec1_boundary_points_on_bbox(
        catchment_area: gpd.GeoDataFrame,
        rec1_network_data: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Get the boundary points where the REC1 rivers intersect with the catchment area boundary.

    Parameters
    -----------
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    rec1_network_data : gpd.GeoDataFrame
        A GeoDataFrame containing the REC1 network data.

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
    # Calculate the centroid of REC1 boundary points and assign it to a new column
    rec1_on_bbox["rec1_boundary_point_centre"] = rec1_on_bbox["rec1_boundary_point"].centroid
    # Set the geometry of the GeoDataFrame to REC1 boundary point centroids
    rec1_bound_points_on_bbox = rec1_on_bbox.set_geometry("rec1_boundary_point_centre")
    # Rename the 'geometry' column to 'rec1_river_line' for better clarity
    rec1_bound_points_on_bbox.rename(columns={'geometry': 'rec1_river_line'}, inplace=True)
    return rec1_bound_points_on_bbox


def get_rec1_network_data_on_bbox(
        catchment_area: gpd.GeoDataFrame,
        rec1_network_data: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Get the REC1 network data that intersects with the catchment area boundary and identifies the corresponding points
    of intersection on the boundary.

    Parameters
    -----------
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    rec1_network_data : gpd.GeoDataFrame
        A GeoDataFrame containing the REC1 network data.

    Returns
    --------
    gpd.GeoDataFrame
        A GeoDataFrame containing the REC1 network data that intersects with the catchment area boundary,
        along with the corresponding points of intersection on the boundary.
    """
    # Get the line segments representing the catchment area boundary
    catchment_boundary_lines = main_river.get_catchment_boundary_lines(catchment_area)
    # Get the boundary points where the REC1 rivers intersect with the catchment area boundary
    rec1_bound_points = get_rec1_boundary_points_on_bbox(catchment_area, rec1_network_data)
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
