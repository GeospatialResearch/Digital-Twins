# -*- coding: utf-8 -*-
"""
This script processes REC1 data to construct a river network for the defined catchment area.
Additionally, it identifies intersections between the REC1 rivers and the catchment area boundary,
providing valuable information for further use.
"""

from typing import Dict

import geopandas as gpd
from shapely.geometry import Point
import networkx as nx

from src.dynamic_boundary_conditions.river import main_river


def add_first_last_coords_to_rec1(rec1_data: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
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
    unique_nodes_dict = {coord_point: i for i, coord_point in enumerate(unique_node_coords)}
    return unique_nodes_dict


def create_rec1_network_data(rec1_data: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Creates river network data for the catchment area using the REC1 data.

    Parameters
    ----------
    rec1_data : gpd.GeoDataFrame
        A GeoDataFrame containing the REC1 data for the catchment area.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the river network data for the catchment area derived from the REC1 data.
    """
    # Add columns for the first and last coordinates of each LineString in the REC1 data
    rec1_network_data = add_first_last_coords_to_rec1(rec1_data)
    # Generate a dictionary that contains the unique node coordinates in the REC1 data
    unique_nodes_dict = get_unique_nodes_dict(rec1_network_data)
    # Map the first coordinates of LineStrings to their corresponding node indices and assign to the "first_node" column
    rec1_network_data["first_node"] = rec1_network_data["first_coord"].apply(lambda x: unique_nodes_dict.get(x, None))
    # Map the last coordinates of LineStrings to their corresponding node indices and assign to the "last_node" column
    rec1_network_data["last_node"] = rec1_network_data["last_coord"].apply(lambda x: unique_nodes_dict.get(x, None))
    return rec1_network_data


def build_rec1_network(rec1_network_data: gpd.GeoDataFrame) -> nx.Graph:
    """
    Builds a river network for the catchment area using the provided river network data.

    Parameters
    ----------
    rec1_network_data : gpd.GeoDataFrame
        A GeoDataFrame containing the river network data for the catchment area derived from the REC1 data.

    Returns
    -------
    nx.Graph
        A networkx Graph representing the river network for the catchment area.
    """
    # Create an empty undirected graph to represent the river network
    rec1_network = nx.Graph()
    # Iterate over each row in rec1_network_data
    for _, row in rec1_network_data.iterrows():
        # Add nodes to the river network with their attributes
        rec1_network.add_nodes_from([(row["first_node"], {"geom": row["first_coord"]})])
        rec1_network.add_nodes_from([(row["last_node"], {"geom": row["last_coord"]})])
        # Add an edge to the river network with its attributes
        rec1_network.add_edge(
            row["first_node"],
            row["last_node"],
            objectid=row["objectid"],
            nzreach=row["nzreach"],
            areakm2=row["areakm2"],
            strm_order=row["strm_order"],
            geometry=row["geometry"])
    return rec1_network


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
