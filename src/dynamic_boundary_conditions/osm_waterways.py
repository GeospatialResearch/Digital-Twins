# -*- coding: utf-8 -*-
"""
This script fetches OpenStreetMap (OSM) waterways data for the defined catchment area.
Additionally, it identifies intersections between the OSM waterways and the catchment area boundary,
providing valuable information for further use.
"""

import pathlib

import geopandas as gpd
from OSMPythonTools.cachingStrategy import CachingStrategy, JSON
from OSMPythonTools.overpass import overpassQueryBuilder, Overpass

from src import config
from src.dynamic_boundary_conditions import main_river


def configure_osm_cache() -> None:
    """
    Change the directory for storing the OSM cache files.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Get the data directory from the environment variable
    data_dir = config.get_env_variable("DATA_DIR", cast_to=pathlib.Path)
    # Define the OSM cache directory
    osm_cache_dir = data_dir / 'osm_cache'
    # Change the directory for storing the OSM cache files
    CachingStrategy.use(JSON, cacheDir=osm_cache_dir)


def fetch_osm_waterways(catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Fetches OpenStreetMap (OSM) waterways data for the specified catchment area.

    Parameters
    ----------
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the retrieved OSM waterways data for the specified catchment area.
    """
    # Convert the catchment area to the desired coordinate reference system (CRS: 4326)
    osm_catchment_area = catchment_area.to_crs(4326)
    # Get the bounding box coordinates of the osm_catchment_area
    min_x, min_y, max_x, max_y = osm_catchment_area.bounds.values[0]
    # Construct an Overpass query to retrieve waterway elements within the specified bounding box
    query = overpassQueryBuilder(
        bbox=[min_y, min_x, max_y, max_x],
        elementType="way",
        selector="waterway",
        out="body",
        includeGeometry=True)
    # Execute the Overpass query to retrieve waterway elements
    waterways = Overpass().query(query, timeout=600)
    # Initialize an empty dictionary to store element information
    element_dict = {
        "id": [],
        "waterway": [],
        "geometry": []
    }
    # Iterate over the retrieved waterway elements
    for element in waterways.elements():
        # Extract and store the ID, waterway type, and geometry of each element
        element_dict["id"].append(element.id())
        element_dict["waterway"].append(element.tag("waterway"))
        element_dict["geometry"].append(element.geometry())
    # Create a GeoDataFrame from the extracted element information
    osm_waterways = gpd.GeoDataFrame(element_dict, crs=osm_catchment_area.crs)
    # Convert the osm_waterways GeoDataFrame to the CRS of the catchment_area
    osm_waterways = osm_waterways.to_crs(catchment_area.crs)
    return osm_waterways


def get_osm_waterways_data(catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Fetches OpenStreetMap (OSM) waterways data for the specified catchment area.
    Only LineString geometries representing waterways of type "river" or "stream" are included.

    Parameters
    ----------
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing only LineString geometries representing waterways of type "river" or "stream".
    """
    # Change the directory for storing the OSM cache files
    configure_osm_cache()
    # Fetch OpenStreetMap (OSM) waterways data for the specified catchment area
    osm_waterways = fetch_osm_waterways(catchment_area)
    # Filter the OSM waterways data to include only LineString geometries
    osm_waterways = osm_waterways[osm_waterways["geometry"].type == "LineString"]
    # Keep only the waterways that have the waterway types "river" or "stream"
    osm_waterways_data = osm_waterways.loc[
        (osm_waterways['waterway'] == 'river') | (osm_waterways['waterway'] == 'stream')]
    # Reset the index of the resulting GeoDataFrame
    osm_waterways_data = osm_waterways_data.reset_index(drop=True)
    return osm_waterways_data


def get_osm_boundary_points_on_bbox(
        catchment_area: gpd.GeoDataFrame,
        osm_waterways_data: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Get the boundary points where the OSM waterways intersect with the catchment area boundary.

    Parameters
    ----------
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    osm_waterways_data : gpd.GeoDataFrame
        A GeoDataFrame containing the OSM waterways data.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the boundary points where the OSM waterways intersect with the
        catchment area boundary.
    """
    # Get the exterior boundary of the catchment area
    catchment_boundary = catchment_area.exterior.iloc[0]
    # Filter OSM waterways data to obtain only the features intersecting with the catchment area boundary
    osm_on_bbox = osm_waterways_data[osm_waterways_data.intersects(catchment_boundary)].reset_index(drop=True)
    # Initialize an empty list to store OSM boundary points
    osm_bound_points = []
    # Iterate over each row in the 'osm_bound_points' GeoDataFrame
    for _, row in osm_on_bbox.iterrows():
        # Get the geometry for the current row
        geometry = row["geometry"]
        # Find the intersection between the catchment area boundary and OSM geometry
        boundary_point = catchment_boundary.intersection(geometry)
        # Append the boundary point to the list
        osm_bound_points.append(boundary_point)
    # Create a new column to store OSM boundary points
    osm_on_bbox["osm_boundary_point"] = gpd.GeoSeries(osm_bound_points, crs=osm_on_bbox.crs)
    # Calculate the centroid of OSM boundary points and assign it to a new column
    osm_on_bbox["osm_boundary_point_centre"] = osm_on_bbox["osm_boundary_point"].centroid
    # Set the geometry of the GeoDataFrame to OSM boundary point centroids
    osm_bound_points_on_bbox = osm_on_bbox.set_geometry("osm_boundary_point_centre")
    # Rename the 'geometry' column to 'osm_waterway_line' for better clarity
    osm_bound_points_on_bbox.rename(columns={'geometry': 'osm_waterway_line'}, inplace=True)
    return osm_bound_points_on_bbox


def get_osm_waterways_data_on_bbox(
        catchment_area: gpd.GeoDataFrame,
        osm_waterways_data: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Get the OSM waterways data that intersects with the catchment area boundary and identifies the corresponding points
    of intersection on the boundary.

    Parameters
    ----------
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    osm_waterways_data : gpd.GeoDataFrame
        A GeoDataFrame containing the OSM waterways data.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the OSM waterways data that intersects with the catchment area boundary,
        along with the corresponding points of intersection on the boundary.
    """
    # Get the line segments representing the catchment area boundary
    catchment_boundary_lines = main_river.get_catchment_boundary_lines(catchment_area)
    # Get the boundary points where the OSM waterways intersect with the catchment area boundary
    osm_bound_points = get_osm_boundary_points_on_bbox(catchment_area, osm_waterways_data)
    # Perform a spatial join between the OSM boundary points and catchment boundary lines
    osm_waterways_data_on_bbox = gpd.sjoin(
        osm_bound_points, catchment_boundary_lines, how='left', predicate='intersects')
    # Remove unnecessary column
    osm_waterways_data_on_bbox.drop(columns=['index_right'], inplace=True)
    # Merge the catchment boundary lines with the OSM waterways data based on boundary line number
    osm_waterways_data_on_bbox = osm_waterways_data_on_bbox.merge(
        catchment_boundary_lines, on='boundary_line_no', how='left').sort_index()
    # Rename the geometry column to 'boundary_line' for better clarity
    osm_waterways_data_on_bbox.rename(columns={'geometry': 'boundary_line'}, inplace=True)
    return osm_waterways_data_on_bbox
