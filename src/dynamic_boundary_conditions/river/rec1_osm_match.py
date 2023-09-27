# -*- coding: utf-8 -*-
"""
This script facilitates the matching of REC1 rivers with OpenStreetMap (OSM) waterways by finding the closest
OSM waterway to each REC1 river. It also determines the target points used for the river input in the BG-Flood model.
"""

from typing import Dict, List, Union

import geopandas as gpd
import pandas as pd
import numpy as np
import xarray as xr
from shapely.geometry import Point
from sqlalchemy.engine import Engine

from src.dynamic_boundary_conditions.river import main_river, osm_waterways
from newzealidar.utils import get_dem_band_and_resolution_by_geometry


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
    hydro_dem_extent = main_river.get_extent_of_hydro_dem(engine, catchment_area)
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
    node_direction = multi_intersect_row['node_direction']
    node_intersect_aoi = multi_intersect_row['node_intersect_aoi']
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
        objectid = multi_intersect_row['objectid']
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
        objectid, boundary_points = row['objectid'], row['rec1_boundary_point_explode']
        # Determines the index that represents the position of the first inflow boundary point
        inflow_index = determine_multi_intersect_inflow_index(row)

        # Initialize a dictionary to categorize boundary points as 'inflow' or 'outflow'
        categorized_points = {'outflow': [], 'inflow': []}
        # Iterate through the list of exploded boundary points and categorize each one
        for index, point in enumerate(boundary_points):
            # Determine the category based on their order along the river segment and inflow index
            category = 'inflow' if index % 2 == inflow_index else 'outflow'
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
    multi_point_inflows['rec1_inflow_point'] = multi_point_inflows['rec1_inflow_point'].astype('geometry')
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
    Obtain REC1 river network segments where water flows into the specified catchment area,
    along with their corresponding inflow boundary points.

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
        A GeoDataFrame containing REC1 river network segments where water flows into the catchment area,
        along with their corresponding inflow boundary points.
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
    hydro_dem_extent = main_river.get_extent_of_hydro_dem(engine, catchment_area)
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
    Aligns the boundary points of REC1 river inflows with the boundary points of OpenStreetMap (OSM) waterways
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
        A GeoDataFrame containing the REC1 river inflow boundary points aligned with the boundary points of
        OpenStreetMap (OSM) waterways within a specified distance threshold.
    """
    # Select relevant columns from REC1 data
    rec1_columns = ['objectid', rec1_inflows_on_bbox.geometry.name]
    rec1_on_bbox = rec1_inflows_on_bbox[rec1_columns]
    # Select relevant columns from OSM data
    osm_columns = ['id', osm_waterways_on_bbox.geometry.name]
    osm_on_bbox = osm_waterways_on_bbox[osm_columns]
    # Perform a spatial join to find the nearest OSM waterway features within a specified distance
    aligned_rec1_osm = gpd.sjoin_nearest(
        rec1_on_bbox, osm_on_bbox, how='inner', distance_col="distances", max_distance=distance_m)
    # Sort the aligned data by distance
    aligned_rec1_osm = aligned_rec1_osm.sort_values(by='distances')
    # Remove duplicate OSM waterway features and keep the closest ones
    aligned_rec1_osm = aligned_rec1_osm.drop_duplicates(subset='id', keep='first')
    # Select relevant columns and merge with OSM waterway data
    aligned_rec1_osm = aligned_rec1_osm[['objectid', 'index_right']]
    aligned_rec1_osm = aligned_rec1_osm.merge(osm_on_bbox, left_on='index_right', right_index=True, how='left')
    # Clean up the resulting GeoDataFrame
    aligned_rec1_osm = aligned_rec1_osm.drop(columns=['index_right']).reset_index(drop=True)
    aligned_rec1_osm = gpd.GeoDataFrame(aligned_rec1_osm, geometry='osm_boundary_point')
    return aligned_rec1_osm


# def identify_inflow_points_around_aoi(
#         engine: Engine,
#         catchment_area: gpd.GeoDataFrame,
#         rec1_network_data: gpd.GeoDataFrame,
#         distance_m: int = 300):
#     """
#     Parameters
#     -----------
#     engine : Engine
#         The engine used to connect to the database.
#     catchment_area : gpd.GeoDataFrame
#         A GeoDataFrame representing the catchment area.
#     rec1_network_data : gpd.GeoDataFrame
#         A GeoDataFrame containing the REC1 river network data.
#     distance_m : int = 300
#         Distance threshold in meters for spatial proximity matching. The default value is 300 meters.
#     """
#     rec1_inflows_on_bbox = get_rec1_inflows_on_bbox(engine, catchment_area, rec1_network_data)
#     osm_waterways_on_bbox = get_osm_waterways_on_bbox(engine, catchment_area)
#     aligned_rec1_osm = align_rec1_with_osm(rec1_inflows_on_bbox, osm_waterways_on_bbox, distance_m=distance_m)
#     # Get the line segments representing the catchment area boundary
#     catchment_boundary_lines = main_river.get_catchment_boundary_lines(catchment_area)
#     # Perform a spatial join between the REC1 boundary points and catchment boundary lines
#     test = gpd.sjoin(rec1_bound_points, catchment_boundary_lines, how='left', predicate='intersects')
#
#     # Retrieve the Hydro DEM data and resolution for the specified catchment area
#     hydro_dem, res_no = get_dem_band_and_resolution_by_geometry(engine, catchment_area)
#     # Initialize an empty GeoDataFrame to store the target locations
#     aligned_rec1_osm_w_target_loc = gpd.GeoDataFrame()
#     # Iterate over each row in the 'closest_osm_waterways' GeoDataFrame
#     for i in range(len(aligned_rec1_osm)):
#         # Extract the current row for processing
#         single_aligned_rec1_osm = aligned_rec1_osm.iloc[i:i + 1].reset_index(drop=True)
#         # Obtain the target location with the minimum elevation from the Hydro DEM to the closest OSM waterway
#         min_elevation_location = get_target_location_from_hydro_dem(single_aligned_rec1_osm, hydro_dem, res_no)
#         # Merge the target location data with the current OSM waterway data
#         single_w_target_loc = single_aligned_rec1_osm.merge(
#             min_elevation_location, how='left', left_index=True, right_index=True)
#         # Append the merged data to the overall GeoDataFrame
#         aligned_rec1_osm_w_target_loc = pd.concat([aligned_rec1_osm_w_target_loc, single_w_target_loc])
#     # Add the Hydro DEM resolution information to the resulting GeoDataFrame
#     aligned_rec1_osm_w_target_loc['dem_resolution'] = res_no
#     # Set the geometry column and reset the index
#     aligned_rec1_osm_w_target_loc = aligned_rec1_osm_w_target_loc.set_geometry('target_point').reset_index(drop=True)
#     return aligned_rec1_osm_w_target_loc
#
#
# def get_target_location_from_hydro_dem(
#         single_closest_osm_waterway: gpd.GeoDataFrame,
#         hydro_dem: xr.Dataset,
#         hydro_dem_resolution: Union[int, float]) -> gpd.GeoDataFrame:
#     # Obtain the nearest elevation values from the Hydro DEM to the closest OSM waterway
#     elevation_values = get_elevations_from_hydro_dem(single_closest_osm_waterway, hydro_dem, hydro_dem_resolution)
#     # Derive the midpoint by determining the centroid of all target points
#     midpoint_coord = elevation_values['target_point'].unary_union.centroid
#     # Calculate the distances between each target point and the midpoint
#     elevation_values['distance'] = elevation_values['target_point'].distance(midpoint_coord)
#     # Find the minimum elevation value
#     min_elevation_value = elevation_values['elevation'].min()
#     # Extract the rows with the minimum elevation value
#     min_elevation_rows = elevation_values[elevation_values['elevation'] == min_elevation_value]
#     # Select the closest point to the midpoint based on the minimum distance
#     min_elevation_location = min_elevation_rows.sort_values('distance').head(1)
#     # Remove unnecessary columns and reset the index
#     min_elevation_location = min_elevation_location.drop(columns=['distance']).reset_index(drop=True)
#     return min_elevation_location
#
#
# def get_elevations_from_hydro_dem(
#         single_closest_osm_waterway: gpd.GeoDataFrame,
#         hydro_dem: xr.Dataset,
#         hydro_dem_resolution: Union[int, float]) -> gpd.GeoDataFrame:
#     # Buffer the boundary line using the Hydro DEM resolution
#     single_closest_osm_waterway['boundary_line_buffered'] = (
#         single_closest_osm_waterway['boundary_line'].buffer(distance=hydro_dem_resolution, cap_style=2))
#     # Clip the Hydro DEM using the buffered boundary line
#     clipped_hydro_dem = hydro_dem.rio.clip(single_closest_osm_waterway['boundary_line_buffered'])
#     # Get the x and y coordinates of the OSM boundary point center
#     osm_boundary_point_centre = single_closest_osm_waterway['osm_boundary_point_centre'].iloc[0]
#     osm_bound_point_x, osm_bound_point_y = osm_boundary_point_centre.x, osm_boundary_point_centre.y
#     # Find the indices of the closest x and y coordinates in the clipped Hydro DEM
#     midpoint_x_index = int(np.argmin(abs(clipped_hydro_dem['x'].values - osm_bound_point_x)))
#     midpoint_y_index = int(np.argmin(abs(clipped_hydro_dem['y'].values - osm_bound_point_y)))
#     # Define the starting and ending indices for the x coordinates in the clipped Hydro DEM
#     start_x_index = max(0, midpoint_x_index - 2)
#     end_x_index = min(midpoint_x_index + 3, len(clipped_hydro_dem['x']))
#     # Define the starting and ending indices for the y coordinates in the clipped Hydro DEM
#     start_y_index = max(0, midpoint_y_index - 2)
#     end_y_index = min(midpoint_y_index + 3, len(clipped_hydro_dem['y']))
#     # Extract the x and y coordinates within the defined range from the clipped Hydro DEM
#     x_range = clipped_hydro_dem['x'].values[slice(start_x_index, end_x_index)]
#     y_range = clipped_hydro_dem['y'].values[slice(start_y_index, end_y_index)]
#     # Extract elevation values for the specified x and y coordinates from the clipped Hydro DEM
#     elevation_values = clipped_hydro_dem.sel(x=x_range, y=y_range).to_dataframe().reset_index()
#     # Create Point objects for each row using 'x' and 'y' coordinates, storing them in 'target_point' column
#     elevation_values['target_point'] = elevation_values.apply(lambda row: Point(row['x'], row['y']), axis=1)
#     # Remove unnecessary columns from the elevation data
#     elevation_values.drop(columns=['x', 'y', 'band', 'spatial_ref', 'data_source', 'lidar_source'], inplace=True)
#     # Rename the 'z' column to 'elevation_value' for clarity and consistency
#     elevation_values.rename(columns={'z': 'elevation'}, inplace=True)
#     # Convert the elevation data to a GeoDataFrame with 'target_point' as the geometry column
#     elevation_values = gpd.GeoDataFrame(elevation_values, geometry='target_point', crs=single_closest_osm_waterway.crs)
#     return elevation_values
#
