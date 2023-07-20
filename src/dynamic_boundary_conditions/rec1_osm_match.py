# -*- coding: utf-8 -*-
"""
@Description: This script facilitates the matching of REC1 rivers with OpenStreetMap (OSM) waterways by finding the
              closest OSM waterway to each REC1 river. It also determines the target points used for the river input
              in the BG-Flood model.
@Author: sli229
"""

import logging
from typing import Union

import geopandas as gpd
import pandas as pd
import numpy as np
import xarray as xr
from shapely.geometry import Point
from sqlalchemy.engine import Engine

from src.lidar import dem_metadata_in_db

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def match_rec1_river_and_osm_waterway(
        rec1_network_data_on_bbox: gpd.GeoDataFrame,
        osm_waterways_data_on_bbox: gpd.GeoDataFrame,
        distance_m: int = 300) -> gpd.GeoDataFrame:
    """
    Matches REC1 network data with OSM waterways data based on their spatial proximity within a specified distance
    threshold.

    Parameters
    ----------
    rec1_network_data_on_bbox : gpd.GeoDataFrame
        A GeoDataFrame containing the REC1 network data that intersects with the catchment area boundary.
    osm_waterways_data_on_bbox : gpd.GeoDataFrame
        A GeoDataFrame containing the OSM waterways data that intersects with the catchment area boundary.
    distance_m : int, optional
        Distance threshold in meters for spatial proximity matching. The default value is 300 meters.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the matched REC1 network data and OSM waterways data, including spatial proximity
        information.
    """
    # Select relevant columns from REC1 network data
    rec1_on_bbox = rec1_network_data_on_bbox[
        ['objectid', 'rec1_boundary_point_centre', 'boundary_line', 'boundary_line_no']]
    # Select relevant columns from OSM waterways data
    osm_on_bbox = osm_waterways_data_on_bbox[
        ['id', 'osm_boundary_point_centre', 'boundary_line', 'boundary_line_no']]
    # Spatially join the REC1 and OSM data based on the nearest distance within the distance threshold
    matched_rec1_and_osm = gpd.sjoin_nearest(rec1_on_bbox, osm_on_bbox, how='inner',
                                             distance_col="distances", max_distance=distance_m)
    # Find duplicated columns
    duplicated_columns = matched_rec1_and_osm.T.duplicated(keep='last')
    # Select the indexes of the duplicated columns to drop
    columns_to_drop = duplicated_columns[duplicated_columns].index
    # Drop the duplicated columns
    matched_rec1_and_osm.drop(columns=columns_to_drop, inplace=True)
    # Rename specific columns for consistency
    matched_rec1_and_osm = matched_rec1_and_osm.rename(
        columns={'boundary_line_right': 'boundary_line', 'boundary_line_no_right': 'boundary_line_no'})
    # Set the 'boundary_line' column as the geometry column
    matched_rec1_and_osm = matched_rec1_and_osm.set_geometry("boundary_line")
    # Drop unnecessary columns
    matched_rec1_and_osm = matched_rec1_and_osm.drop(columns=['rec1_boundary_point_centre', 'index_right'])
    # Sort the matched data based on the 'distances' column
    matched_rec1_and_osm = matched_rec1_and_osm.sort_values(by='distances')
    # Drop duplicate rows based on the 'id' column, keeping the first occurrence
    matched_rec1_and_osm = matched_rec1_and_osm.drop_duplicates(subset='id', keep='first')
    # Sort the matched data based on the 'boundary_line_no' column and reset the index
    matched_rec1_and_osm = matched_rec1_and_osm.sort_values(by='boundary_line_no').reset_index(drop=True)
    return matched_rec1_and_osm


def find_closest_osm_waterways(
        rec1_network_data_on_bbox: gpd.GeoDataFrame,
        osm_waterways_data_on_bbox: gpd.GeoDataFrame,
        distance_m: int = 300) -> gpd.GeoDataFrame:
    """
    Finds the closest OSM waterway to each REC1 river within the specified distance threshold.

    Parameters
    ----------
    rec1_network_data_on_bbox : gpd.GeoDataFrame
        A GeoDataFrame containing the REC1 network data that intersects with the catchment area boundary.
    osm_waterways_data_on_bbox : gpd.GeoDataFrame
        A GeoDataFrame containing the OSM waterways data that intersects with the catchment area boundary.
    distance_m : int, optional
        Distance threshold in meters for determining the closest OSM waterway. The default value is 300 meters.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the closest OSM waterway to each REC1 river.
    """
    # Match REC1 and OSM data based on proximity
    matched_rec1_and_osm = match_rec1_river_and_osm_waterway(
        rec1_network_data_on_bbox, osm_waterways_data_on_bbox, distance_m)
    # Extract REC1 object IDs and OSM IDs from the matched REC1 and OSM data
    closest_osm_waterway_ids = matched_rec1_and_osm[['objectid', 'id']]
    # Merge the extracted REC1 object IDs and OSM IDs with the original OSM waterways data
    closest_osm_waterways = closest_osm_waterway_ids.merge(osm_waterways_data_on_bbox, on='id', how='left')
    # Drop the 'waterway' column from the merged data
    closest_osm_waterways.drop(columns=['waterway'], inplace=True)
    # Convert the merged data to a GeoDataFrame and set the geometry column
    closest_osm_waterways = gpd.GeoDataFrame(closest_osm_waterways, geometry='osm_boundary_point_centre')
    return closest_osm_waterways


def get_elevations_from_hydro_dem(
        single_closest_osm_waterway: gpd.GeoDataFrame,
        hydro_dem: xr.Dataset,
        hydro_dem_resolution: Union[int, float]) -> gpd.GeoDataFrame:
    """
    Extracts the nearest elevation values from the Hydrologically Conditioned DEM (Hydro DEM) for the area
    surrounding the closest OpenStreetMap (OSM) waterway, along with their corresponding coordinates.

    Parameters
    ----------
    single_closest_osm_waterway : gpd.GeoDataFrame
        A GeoDataFrame representing a single row of the closest OSM waterways.
    hydro_dem : xr.Dataset
        Hydrologically Conditioned DEM (Hydro DEM) for the catchment area.
    hydro_dem_resolution: Union[int, float]
        Resolution of the Hydrologically Conditioned DEM (Hydro DEM).

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the nearest elevation values extracted from the Hydrologically Conditioned DEM
        (Hydro DEM) for the area surrounding the closest OSM waterway, along with their corresponding coordinates.
    """
    # Buffer the boundary line using the Hydro DEM resolution
    single_closest_osm_waterway['boundary_line_buffered'] = (
        single_closest_osm_waterway['boundary_line'].buffer(distance=hydro_dem_resolution, cap_style=2))
    # Clip the Hydro DEM using the buffered boundary line
    clipped_hydro_dem = hydro_dem.rio.clip(single_closest_osm_waterway['boundary_line_buffered'])
    # Get the x and y coordinates of the OSM boundary point center
    osm_boundary_point_centre = single_closest_osm_waterway['osm_boundary_point_centre'].iloc[0]
    osm_bound_point_x, osm_bound_point_y = osm_boundary_point_centre.x, osm_boundary_point_centre.y
    # Find the indices of the closest x and y coordinates in the clipped Hydro DEM
    midpoint_x_index = int(np.argmin(abs(clipped_hydro_dem['x'].values - osm_bound_point_x)))
    midpoint_y_index = int(np.argmin(abs(clipped_hydro_dem['y'].values - osm_bound_point_y)))
    # Define the starting and ending indices for the x coordinates in the clipped Hydro DEM
    start_x_index = max(0, midpoint_x_index - 2)
    end_x_index = min(midpoint_x_index + 3, len(clipped_hydro_dem['x']))
    # Define the starting and ending indices for the y coordinates in the clipped Hydro DEM
    start_y_index = max(0, midpoint_y_index - 2)
    end_y_index = min(midpoint_y_index + 3, len(clipped_hydro_dem['y']))
    # Extract the x and y coordinates within the defined range from the clipped Hydro DEM
    x_range = clipped_hydro_dem['x'].values[slice(start_x_index, end_x_index)]
    y_range = clipped_hydro_dem['y'].values[slice(start_y_index, end_y_index)]
    # Extract elevation values for the specified x and y coordinates from the clipped Hydro DEM
    elevation_values = clipped_hydro_dem.sel(x=x_range, y=y_range).to_dataframe().reset_index()
    # Create Point objects for each row using 'x' and 'y' coordinates, storing them in 'target_point' column
    elevation_values['target_point'] = elevation_values.apply(lambda row: Point(row['x'], row['y']), axis=1)
    # Remove unnecessary columns from the elevation data
    elevation_values.drop(columns=['x', 'y', 'band', 'spatial_ref', 'source_class'], inplace=True)
    # Rename the 'z' column to 'elevation_value' for clarity and consistency
    elevation_values.rename(columns={'z': 'elevation'}, inplace=True)
    # Convert the elevation data to a GeoDataFrame with 'target_point' as the geometry column
    elevation_values = gpd.GeoDataFrame(elevation_values, geometry='target_point', crs=single_closest_osm_waterway.crs)
    return elevation_values


def get_target_location_from_hydro_dem(
        single_closest_osm_waterway: gpd.GeoDataFrame,
        hydro_dem: xr.Dataset,
        hydro_dem_resolution: Union[int, float]) -> gpd.GeoDataFrame:
    """
    Get the target location with the minimum elevation from the Hydrologically Conditioned DEM (Hydro DEM)
    to the closest OpenStreetMap (OSM) waterway. This location is crucial for the river input in the BG-Flood model,
    as it enables precise identification of where to add the river as a vertical discharge.

    Parameters
    ----------
    single_closest_osm_waterway : gpd.GeoDataFrame
        A GeoDataFrame representing a single row of the closest OSM waterways.
    hydro_dem : xr.Dataset
        Hydrologically Conditioned DEM (Hydro DEM) for the catchment area.
    hydro_dem_resolution: Union[int, float]
        Resolution of the Hydrologically Conditioned DEM (Hydro DEM).

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the target location (Point) with the minimum elevation from the Hydrologically
        Conditioned DEM (Hydro DEM) to the closest OSM waterway.
    """
    # Obtain the nearest elevation values from the Hydro DEM to the closest OSM waterway
    elevation_values = get_elevations_from_hydro_dem(single_closest_osm_waterway, hydro_dem, hydro_dem_resolution)
    # Derive the midpoint by determining the centroid of all target points
    midpoint_coord = elevation_values['target_point'].unary_union.centroid
    # Calculate the distances between each target point and the midpoint
    elevation_values['distance'] = elevation_values['target_point'].distance(midpoint_coord)
    # Find the minimum elevation value
    min_elevation_value = elevation_values['elevation'].min()
    # Extract the rows with the minimum elevation value
    min_elevation_rows = elevation_values[elevation_values['elevation'] == min_elevation_value]
    # Select the closest point to the midpoint based on the minimum distance
    min_elevation_location = min_elevation_rows.sort_values('distance').head(1)
    # Remove unnecessary columns and reset the index
    min_elevation_location = min_elevation_location.drop(columns=['distance']).reset_index(drop=True)
    return min_elevation_location


def get_closest_osm_waterways_with_target_locations(
        engine: Engine,
        catchment_area: gpd.GeoDataFrame,
        rec1_network_data_on_bbox: gpd.GeoDataFrame,
        osm_waterways_data_on_bbox: gpd.GeoDataFrame,
        distance_m: int = 300) -> gpd.GeoDataFrame:
    """
    Get the closest OpenStreetMap (OSM) waterway to each REC1 river within the specified distance threshold,
    along with the identified target locations used for the river input in the BG-Flood model.

    Parameters
    ----------
    engine : Engine
        Engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    rec1_network_data_on_bbox : gpd.GeoDataFrame
        A GeoDataFrame containing the REC1 network data that intersects with the catchment area boundary.
    osm_waterways_data_on_bbox : gpd.GeoDataFrame
        A GeoDataFrame containing the OSM waterways data that intersects with the catchment area boundary.
    distance_m : int, optional
        Distance threshold in meters for determining the closest OSM waterway. The default value is 300 meters.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the closest OSM waterway to each REC1 river, along with the identified
        target locations used for the river input in the BG-Flood model.
    """
    # Find the closest OSM waterway to each REC1 river within the specified distance threshold
    closest_osm_waterways = find_closest_osm_waterways(
        rec1_network_data_on_bbox, osm_waterways_data_on_bbox, distance_m)
    # Retrieve the Hydro DEM data and resolution for the specified catchment area
    hydro_dem, res_no = dem_metadata_in_db.get_hydro_dem_data_and_resolution(engine, catchment_area)
    # Initialize an empty GeoDataFrame to store the target locations
    closest_waterways_w_target_loc = gpd.GeoDataFrame()
    # Iterate over each row in the 'closest_osm_waterways' GeoDataFrame
    for i in range(len(closest_osm_waterways)):
        # Extract the current row for processing
        single_closest_osm_waterway = closest_osm_waterways.iloc[i:i + 1].reset_index(drop=True)
        # Obtain the target location with the minimum elevation from the Hydro DEM to the closest OSM waterway
        min_elevation_location = get_target_location_from_hydro_dem(single_closest_osm_waterway, hydro_dem, res_no)
        # Merge the target location data with the current OSM waterway data
        single_w_target_loc = single_closest_osm_waterway.merge(
            min_elevation_location, how='left', left_index=True, right_index=True)
        # Append the merged data to the overall GeoDataFrame
        closest_waterways_w_target_loc = pd.concat([closest_waterways_w_target_loc, single_w_target_loc])
    # Add the Hydro DEM resolution information to the resulting GeoDataFrame
    closest_waterways_w_target_loc['dem_resolution'] = res_no
    # Set the geometry column and reset the index
    closest_waterways_w_target_loc = closest_waterways_w_target_loc.set_geometry('target_point').reset_index(drop=True)
    return closest_waterways_w_target_loc


def get_matched_data_with_target_locations(
        engine: Engine,
        catchment_area: gpd.GeoDataFrame,
        rec1_network_data_on_bbox: gpd.GeoDataFrame,
        osm_waterways_data_on_bbox: gpd.GeoDataFrame,
        distance_m: int = 300) -> gpd.GeoDataFrame:
    """
    Get the matched data between REC1 rivers and OSM waterways within the specified distance threshold,
    along with the identified target locations used for the river input in the BG-Flood model.

    Parameters
    ----------
    engine : Engine
        Engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    rec1_network_data_on_bbox : gpd.GeoDataFrame
        A GeoDataFrame containing the REC1 network data that intersects with the catchment area boundary.
    osm_waterways_data_on_bbox : gpd.GeoDataFrame
        A GeoDataFrame containing the OSM waterways data that intersects with the catchment area boundary.
    distance_m : int, optional
        Distance threshold in meters for determining the closest OSM waterway. The default value is 300 meters.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the matched data between REC1 rivers and OSM waterways, along with the identified
        target locations used for the river input in the BG-Flood model.
    """
    # Get the closest OSM waterway to each REC1 river along with the identified target locations used for BG-Flood
    closest_osm_waterways_with_target_locations = get_closest_osm_waterways_with_target_locations(
        engine, catchment_area, rec1_network_data_on_bbox, osm_waterways_data_on_bbox, distance_m)
    # Merge REC1 network data with the closest OSM waterways
    matched_data = rec1_network_data_on_bbox.merge(
        closest_osm_waterways_with_target_locations, on='objectid', how='right')
    # Drop unnecessary columns from the merged data
    matched_data.drop(columns=['boundary_line_no_x', 'boundary_line_x'], inplace=True)
    # Rename specific columns for consistency
    matched_data = matched_data.rename(
        columns={'boundary_line_no_y': 'boundary_line_no', 'boundary_line_y': 'boundary_line'})
    # Set the geometry column
    matched_data = matched_data.set_geometry("target_point")
    return matched_data
