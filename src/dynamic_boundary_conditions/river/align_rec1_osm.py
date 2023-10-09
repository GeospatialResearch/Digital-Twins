# -*- coding: utf-8 -*-
"""
This script handles the task of obtaining data for REC1 river inflow segments whose boundary points align with the
boundary points of OpenStreetMap (OSM) waterways within a specified distance threshold.
"""

from typing import Dict, List

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from sqlalchemy.engine import Engine

from src.dynamic_boundary_conditions.river import main_river, osm_waterways


def get_rec1_network_data_on_bbox(
        engine: Engine,
        catchment_area: gpd.GeoDataFrame,
        rec1_network_data: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Obtain REC1 river network data that intersects with the catchment area boundary, along with the corresponding
    intersection points on the boundary.

    Parameters
    -----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    rec1_network_data : gpd.GeoDataFrame
        A GeoDataFrame containing the REC1 river network data.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing REC1 river network data that intersects with the catchment area boundary,
        along with the corresponding intersection points on the boundary.
    """
    # Obtain the spatial extent of the hydro DEM
    _, hydro_dem_extent, _ = main_river.get_hydro_dem_extent(engine, catchment_area)
    # Select features that intersect with the hydro DEM extent
    rec1_on_bbox = rec1_network_data[rec1_network_data.intersects(hydro_dem_extent)].reset_index(drop=True)
    # Determine the points of intersection along the boundary
    rec1_on_bbox["rec1_boundary_point"] = rec1_on_bbox["geometry"].intersection(hydro_dem_extent)
    # Rename the 'geometry' column to 'rec1_river_line' and set the geometry to 'rec1_boundary_point'
    rec1_on_bbox = rec1_on_bbox.rename_geometry("rec1_river_line").set_geometry("rec1_boundary_point")
    return rec1_on_bbox


def get_single_intersect_inflows(rec1_on_bbox: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Identifies REC1 river segments that intersect the catchment boundary once, then retrieves the segments
    that are inflows into the catchment area, along with their corresponding inflow boundary points.

    Parameters
    ----------
    rec1_on_bbox : gpd.GeoDataFrame
        A GeoDataFrame containing REC1 river network data that intersects with the catchment area boundary,
        along with the corresponding intersection points on the boundary.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the REC1 river segments that intersect the catchment boundary once and
        are inflows into the catchment area, along with their corresponding inflow boundary points.
    """
    # Select only the records where 'rec1_boundary_point' is a single point
    single_intersect = rec1_on_bbox[rec1_on_bbox["rec1_boundary_point"].geom_type == "Point"]
    # Identify the inflow boundary points
    single_intersect_inflow = single_intersect[
        ((single_intersect["node_direction"] == "to") & (single_intersect["node_intersect_aoi"] == "last_node")) |
        ((single_intersect["node_direction"] == "from") & (single_intersect["node_intersect_aoi"] == "first_node"))
        ]
    # Create a new column for inflow points for consistency purposes
    single_intersect_inflow["rec1_inflow_point"] = single_intersect_inflow["rec1_boundary_point"]
    # Set the geometry of the GeoDataFrame to 'rec1_inflow_point'
    single_intersect_inflow.set_geometry("rec1_inflow_point", inplace=True)
    # Reset the index
    single_intersect_inflow.reset_index(drop=True, inplace=True)
    return single_intersect_inflow


def get_exploded_multi_intersect(rec1_on_bbox: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Identifies REC1 river segments that intersect the catchment boundary multiple times,
    transforms MultiPoint geometries into individual Point geometries (boundary points),
    calculates the distance along the river segment for each boundary point, and
    adds a new column containing boundary points sorted by their distance along the river.

    Parameters
    ----------
    rec1_on_bbox : gpd.GeoDataFrame
        A GeoDataFrame containing REC1 river network data that intersects with the catchment area boundary,
        along with the corresponding intersection points on the boundary.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the REC1 river segments that intersect the catchment boundary multiple times,
        along with the corresponding intersection points on the boundary, sorted by distance along the river.
    """
    # Select only the records where 'rec1_boundary_point' is a collection of multiple points (MultiPoint)
    multi_intersect = rec1_on_bbox[rec1_on_bbox["rec1_boundary_point"].geom_type == "MultiPoint"]
    # Explode multi-part geometries into multiple single geometries
    multi_intersect_explode = multi_intersect.explode()
    # Calculate the distance along the river for each Point and add it as a new column
    multi_intersect_explode["distance_along_river"] = multi_intersect_explode.apply(
        lambda row: row["rec1_river_line"].project(row["rec1_boundary_point"]), axis=1)
    # Sort the exploded points by 'objectid' and 'distance_along_river'
    multi_intersect_explode.sort_values(by=["objectid", "distance_along_river"], inplace=True)
    # Group the exploded Points by 'objectid' and collect them as a list (already sorted by distance along the river)
    exploded_intersect_by_distance = (
        multi_intersect_explode
        .groupby("objectid")["rec1_boundary_point"]
        .apply(list)
        .reset_index(name="rec1_boundary_point_explode")
    )
    # Merge the list of exploded boundary points back
    multi_intersect = multi_intersect.merge(exploded_intersect_by_distance, on="objectid", how="left")
    return multi_intersect


def determine_multi_intersect_inflow_index(multi_intersect_row: pd.Series) -> int:
    """
    Determines the index that represents the position of the first inflow boundary point along a REC1 river segment.

    Parameters
    ----------
    multi_intersect_row : pd.Series
        A REC1 river segment that intersects the catchment boundary multiple times, along with the
        corresponding intersection points on the boundary, sorted by distance along the river.

    Returns
    -------
    int
        An integer that represents the position of the first inflow boundary point along a REC1 river segment.

    Raises
    ------
    ValueError
        If the index that represents the position of the first inflow boundary point along a REC1 river segment
        cannot be determined.
    """
    # Extract the 'node_direction' and 'node_intersect_aoi' attributes from the input Series
    node_direction = multi_intersect_row["node_direction"]
    node_intersect_aoi = multi_intersect_row["node_intersect_aoi"]
    # Define a dictionary to map conditions to inflow_index values
    condition_mapping = {
        ("to", "both_nodes"): 1,
        ("to", "first_node"): 1,
        ("from", None): 1,
        ("from", "last_node"): 1,
        ("from", "both_nodes"): 0,
        ("from", "first_node"): 0,
        ("to", None): 0,
        ("to", "last_node"): 0,
    }
    # Check if the condition exists in the dictionary, otherwise default to None
    inflow_index = condition_mapping.get((node_direction, node_intersect_aoi), None)
    # If none of the conditions are met, raise a ValueError with an informative message
    if inflow_index is None:
        objectid = multi_intersect_row["objectid"]
        raise ValueError(f"Unable to determine the inflow index for REC1 river segment {objectid}.")
    return inflow_index


def categorize_exploded_multi_intersect(multi_intersect: gpd.GeoDataFrame) -> Dict[int, Dict[str, List[Point]]]:
    """
    Categorizes boundary points of REC1 river segments that intersect the catchment boundary multiple times into
    'inflow' and 'outflow' based on their sequential positions along the river segment etc.

    Parameters
    ----------
    multi_intersect : gpd.GeoDataFrame
        A GeoDataFrame containing the REC1 river segments that intersect the catchment boundary multiple times,
        along with the corresponding intersection points on the boundary, sorted by distance along the river.

    Returns
    -------
    Dict[int, Dict[str, List[Point]]]
        A dictionary where the keys represent the 'objectid' values of REC1 river segments, and the values are
        dictionaries. Each of these dictionaries contains two lists: 'inflow' and 'outflow,' which respectively
        represent the boundary points where water flows into and out of the catchment area.
    """
    # Initialize an empty dictionary to store categorized boundary points for each REC1 river segment
    categorized_multi_intersect: Dict[int, Dict[str, List[Point]]] = {}

    # Iterate through each REC1 river segment
    for _, row in multi_intersect.iterrows():
        # Extract the 'objectid' and list of exploded boundary points
        objectid, boundary_points = row["objectid"], row["rec1_boundary_point_explode"]
        # Determines the index that represents the position of the first inflow boundary point
        inflow_index = determine_multi_intersect_inflow_index(row)

        # Initialize a dictionary to categorize boundary points as 'inflow' or 'outflow'
        categorized_points = dict(outflow=[], inflow=[])
        # Iterate through the list of exploded boundary points and categorize each one
        for index, point in enumerate(boundary_points):
            # Determine the category based on their order along the river segment and inflow index
            category = "inflow" if index % 2 == inflow_index else "outflow"
            # Append the current 'point' to the appropriate category
            categorized_points[category].append(point)

        # Associate the categorized points with the 'objectid' and store them in the main dictionary
        categorized_multi_intersect[objectid] = categorized_points
    return categorized_multi_intersect


def get_multi_intersect_inflows(rec1_on_bbox: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Identifies REC1 river segments that intersect the catchment boundary multiple times, then retrieves the segments
    that are inflows into the catchment area, along with their corresponding inflow boundary points.

    Parameters
    ----------
    rec1_on_bbox : gpd.GeoDataFrame
        A GeoDataFrame containing REC1 river network data that intersects with the catchment area boundary,
        along with the corresponding intersection points on the boundary.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the REC1 river segments that intersect the catchment boundary multiple times and
        are inflows into the catchment area, along with their corresponding inflow boundary points.
    """
    # Identify and explode MultiPoint geometries into individual Point geometries
    multi_intersect = get_exploded_multi_intersect(rec1_on_bbox)
    # Categorize the exploded Point geometries into 'inflow' and 'outflow' categories
    categorized_multi_intersect = categorize_exploded_multi_intersect(multi_intersect)
    # Extract the 'objectid' and the last inflow point for each REC1 river segment
    inflow_points = [(objectid, data["inflow"][-1]) for objectid, data in categorized_multi_intersect.items()]
    # Create a DataFrame from the extracted inflow points with columns 'objectid' and 'rec1_inflow_point'
    inflow_points_df = pd.DataFrame(inflow_points, columns=["objectid", "rec1_inflow_point"])
    # Merge the inflow points DataFrame with the original MultiPoint GeoDataFrame
    multi_point_inflows = multi_intersect.merge(inflow_points_df, on="objectid", how="left")
    # Convert the 'rec1_inflow_point' column to a geometry data type
    multi_point_inflows["rec1_inflow_point"] = multi_point_inflows["rec1_inflow_point"].astype("geometry")
    # Set the geometry column and coordinate reference system (CRS) for the GeoDataFrame
    multi_point_inflows = multi_point_inflows.set_geometry("rec1_inflow_point", crs=multi_point_inflows.crs)
    # Drop the temporary column used for exploding MultiPoint geometries
    multi_point_inflows = multi_point_inflows.drop(columns=["rec1_boundary_point_explode"])
    # Reset the index
    multi_point_inflows.reset_index(drop=True, inplace=True)
    return multi_point_inflows


def get_rec1_inflows_on_bbox(
        engine: Engine,
        catchment_area: gpd.GeoDataFrame,
        rec1_network_data: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Obtain REC1 river segments that are inflows into the specified catchment area, along with their corresponding
    inflow boundary points.

    Parameters
    -----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    rec1_network_data : gpd.GeoDataFrame
        A GeoDataFrame containing the REC1 river network data.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing REC1 river segments that are inflows into the catchment area, along with their
        corresponding inflow boundary points.
    """
    # Get REC1 river network segments that intersect with the catchment area boundary
    rec1_on_bbox = get_rec1_network_data_on_bbox(engine, catchment_area, rec1_network_data)
    # Get REC1 river segments that intersect the catchment boundary once and flow into the catchment area
    single_intersect_inflow = get_single_intersect_inflows(rec1_on_bbox)
    # Get REC1 river segments that intersect the catchment boundary multiple times and flow into the catchment area
    multi_intersect_inflow = get_multi_intersect_inflows(rec1_on_bbox)
    # Combine inflows from both single and multiple intersection segments into a single GeoDataFrame
    combined_inflows = pd.concat([single_intersect_inflow, multi_intersect_inflow], ignore_index=True)
    rec1_inflows_on_bbox = gpd.GeoDataFrame(combined_inflows)
    return rec1_inflows_on_bbox


def get_osm_waterways_on_bbox(
        engine: Engine,
        catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Retrieve OpenStreetMap (OSM) waterway data that intersects with the catchment area boundary,
    along with the corresponding intersection points on the boundary.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing OpenStreetMap (OSM) waterway data that intersects with the catchment boundary,
        along with the corresponding intersection points on the boundary.
    """
    # Fetch OSM waterway data for the catchment area
    osm_waterways_data = osm_waterways.get_osm_waterways_data(catchment_area)
    # Obtain the spatial extent of the hydro DEM
    _, hydro_dem_extent, _ = main_river.get_hydro_dem_extent(engine, catchment_area)
    # Select features that intersect with the hydro DEM extent
    osm_waterways_on_bbox = osm_waterways_data[osm_waterways_data.intersects(hydro_dem_extent)].reset_index(drop=True)
    # Determine the points of intersection along the boundary
    osm_waterways_on_bbox["osm_boundary_point"] = osm_waterways_on_bbox["geometry"].intersection(hydro_dem_extent)
    # Rename the 'geometry' column to 'osm_river_line' and set the geometry to 'osm_boundary_point'
    osm_waterways_on_bbox = osm_waterways_on_bbox.rename_geometry("osm_river_line").set_geometry("osm_boundary_point")
    # Explode multi-part geometries into multiple single geometries
    osm_waterways_on_bbox = osm_waterways_on_bbox.explode(ignore_index=True)
    return osm_waterways_on_bbox


def align_rec1_with_osm(
        rec1_inflows_on_bbox: gpd.GeoDataFrame,
        osm_waterways_on_bbox: gpd.GeoDataFrame,
        distance_m: int = 300) -> gpd.GeoDataFrame:
    """
    Aligns the boundary points of REC1 river inflow segments with the boundary points of OpenStreetMap (OSM) waterways
    within a specified distance threshold.

    Parameters
    ----------
    rec1_inflows_on_bbox : gpd.GeoDataFrame
        A GeoDataFrame containing REC1 river network segments where water flows into the catchment area,
        along with their corresponding inflow boundary points.
    osm_waterways_on_bbox : gpd.GeoDataFrame
        A GeoDataFrame containing OpenStreetMap (OSM) waterway data that intersects with the catchment boundary,
        along with the corresponding intersection points on the boundary.
    distance_m : int = 300
        Distance threshold in meters for spatial proximity matching. The default value is 300 meters.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the boundary points of REC1 river inflow segments aligned with the boundary points of
        OpenStreetMap (OSM) waterways within a specified distance threshold.
    """
    # Select relevant columns from REC1 data
    rec1_columns = ["objectid", rec1_inflows_on_bbox.geometry.name]
    rec1_on_bbox = rec1_inflows_on_bbox[rec1_columns]
    # Select relevant columns from OSM data
    osm_columns = ["id", osm_waterways_on_bbox.geometry.name]
    osm_on_bbox = osm_waterways_on_bbox[osm_columns]
    # Perform a spatial join to find the nearest OSM waterway features within a specified distance
    aligned_rec1_osm = gpd.sjoin_nearest(
        rec1_on_bbox, osm_on_bbox, how="inner", distance_col="distances", max_distance=distance_m)
    # Sort the aligned data by distance
    aligned_rec1_osm = aligned_rec1_osm.sort_values(by="distances")
    # Remove duplicate OSM waterway features and keep the closest ones
    aligned_rec1_osm = aligned_rec1_osm.drop_duplicates(subset="id", keep="first")
    # Select relevant columns and merge with OSM waterway data
    aligned_rec1_osm = aligned_rec1_osm[["objectid", "index_right"]]
    aligned_rec1_osm = aligned_rec1_osm.merge(osm_on_bbox, left_on="index_right", right_index=True, how="left")
    # Drop the 'index_right' column to clean up the DataFrame
    aligned_rec1_osm = aligned_rec1_osm.drop(columns=["index_right"]).reset_index(drop=True)
    # Create a GeoDataFrame using the 'osm_boundary_point' column as the geometry
    aligned_rec1_osm = gpd.GeoDataFrame(aligned_rec1_osm, geometry="osm_boundary_point")
    # Rename the geometry column to 'aligned_rec1_entry_point' for clarity
    aligned_rec1_osm = aligned_rec1_osm.rename_geometry("aligned_rec1_entry_point")
    return aligned_rec1_osm


def get_rec1_inflows_aligned_to_osm(
        engine: Engine,
        catchment_area: gpd.GeoDataFrame,
        rec1_network_data: gpd.GeoDataFrame,
        distance_m: int = 300) -> gpd.GeoDataFrame:
    """
    Obtain data for REC1 river inflow segments whose boundary points align with the boundary points of
    OpenStreetMap (OSM) waterways within a specified distance threshold.

    Parameters
    -----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    rec1_network_data : gpd.GeoDataFrame
        A GeoDataFrame containing the REC1 river network data.
    distance_m : int = 300
        Distance threshold in meters for spatial proximity matching. The default value is 300 meters.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing data for REC1 river inflow segments whose boundary points align with the
        boundary points of OpenStreetMap (OSM) waterways within a specified distance threshold.
    """
    # Obtain REC1 river network segments where water flows into the catchment area
    rec1_inflows_on_bbox = get_rec1_inflows_on_bbox(engine, catchment_area, rec1_network_data)
    # Retrieve OpenStreetMap (OSM) waterway data that intersects with the catchment area boundary
    osm_waterways_on_bbox = get_osm_waterways_on_bbox(engine, catchment_area)
    # Align REC1 river inflow boundary points with OSM waterway boundary points within the specified distance
    aligned_rec1_osm = align_rec1_with_osm(rec1_inflows_on_bbox, osm_waterways_on_bbox, distance_m)
    # Extract relevant columns
    aligned_rec1_entry_points = aligned_rec1_osm[["objectid", "aligned_rec1_entry_point"]]
    # Combine aligned REC1 entry points with REC1 inflows data
    aligned_rec1_inflows = aligned_rec1_entry_points.merge(rec1_inflows_on_bbox, on="objectid", how="left")
    # Move the 'aligned_rec1_entry_point' column to the last position
    aligned_rec1_inflows["aligned_rec1_entry_point"] = aligned_rec1_inflows.pop("aligned_rec1_entry_point")
    # Drop unnecessary column
    aligned_rec1_inflows.drop(columns=["rec1_inflow_point"], inplace=True)
    return aligned_rec1_inflows
