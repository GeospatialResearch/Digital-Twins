# -*- coding: utf-8 -*-
"""
@Description:
@Author: sli229
"""

import logging

from shapely.geometry import LineString, Point
import geopandas as gpd
from sqlalchemy.engine import Engine

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


class NoTideDataException(Exception):
    pass


def get_regional_council_clipped_from_db(engine: Engine, catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    catchment_polygon = catchment_area["geometry"][0]
    query = f"""
    SELECT *
    FROM region_geometry_clipped AS rgc
    WHERE ST_Intersects(rgc.geometry, ST_GeomFromText('{catchment_polygon}', 2193))"""
    regions_clipped = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry")
    return regions_clipped


def get_nz_coastline_from_db(engine: Engine, catchment_area: gpd.GeoDataFrame, distance_km: int) -> gpd.GeoDataFrame:
    distance_m = distance_km * 1000
    catchment_area_buffered = catchment_area.buffer(distance=distance_m, join_style=2)
    catchment_area_buffered_polygon = catchment_area_buffered.iloc[0]
    query = f"""
    SELECT *
    FROM "_50258-nz-coastlines" AS coast
    WHERE ST_Intersects(coast.geometry, ST_GeomFromText('{catchment_area_buffered_polygon}', 2193))"""
    coastline = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry")
    return coastline


def get_catchment_boundary_info(catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    # Get the exterior boundary of the catchment polygon
    boundary_lines = catchment_area["geometry"][0].exterior.coords
    # Create an empty list to store boundary segment properties
    boundary_segments = []
    # Loop through each boundary line segment
    for i in range(len(boundary_lines) - 1):
        # Get the start and end points of the current boundary segment
        start_point = boundary_lines[i]
        end_point = boundary_lines[i + 1]
        # Find the centroid of the current boundary segment
        centroid = Point((start_point[0] + end_point[0]) / 2, (start_point[1] + end_point[1]) / 2)
        # Determine the position of the centroid relative to the catchment polygon
        if centroid.x == min(boundary_lines)[0]:
            position = 'left'
        elif centroid.x == max(boundary_lines)[0]:
            position = 'right'
        elif centroid.y == min(boundary_lines)[1]:
            position = 'bot'
        elif centroid.y == max(boundary_lines)[1]:
            position = 'top'
        else:
            raise ValueError("Failed to identify catchment boundary line position.")
        # Create a LineString object for the current boundary segment
        segment = LineString([start_point, end_point])
        # Add the boundary segment and its properties to the list
        boundary_segments.append({'line_position': position, 'centroid': centroid, 'boundary': segment})
    # Convert the list to a GeoDataFrame
    boundary_info = gpd.GeoDataFrame(boundary_segments, geometry='boundary', crs=catchment_area.crs)
    return boundary_info


def get_catchment_boundary_lines(catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    boundary_info = get_catchment_boundary_info(catchment_area)
    boundary_lines = boundary_info[['line_position', 'boundary']].rename(columns={'boundary': 'geometry'})
    boundary_lines = boundary_lines.set_geometry('geometry', crs=catchment_area.crs)
    return boundary_lines


def get_catchment_boundary_centroids(catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    boundary_info = get_catchment_boundary_info(catchment_area)
    boundary_centroids = boundary_info[['line_position', 'centroid']].rename(columns={'centroid': 'geometry'})
    boundary_centroids = boundary_centroids.set_geometry('geometry', crs=catchment_area.crs)
    return boundary_centroids


def get_non_intersection_centroid_position(
        catchment_area: gpd.GeoDataFrame,
        non_intersection: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    boundary_lines = get_catchment_boundary_lines(catchment_area)
    non_intersection = non_intersection.explode(index_parts=False, ignore_index=True)
    non_intersection['centroid'] = non_intersection.centroid
    for index, row in non_intersection.iterrows():
        centroid = row['centroid']
        # Calculate the distance from the centroid to each line
        distances = {}
        for _, boundary_row in boundary_lines.iterrows():
            distances[boundary_row['line_position']] = centroid.distance(boundary_row['geometry'])
        # Find the name of the closest line based on the minimum distance
        closest_line = min(distances, key=distances.get)
        non_intersection.at[index, 'position'] = closest_line
    non_intersection = non_intersection[['position', 'centroid']].rename(columns={'centroid': 'geometry'})
    non_intersection = non_intersection.set_geometry('geometry')
    return non_intersection


def get_tide_query_locations(
        engine: Engine,
        catchment_area: gpd.GeoDataFrame,
        regions_clipped: gpd.GeoDataFrame,
        distance_km: int = 1) -> gpd.GeoDataFrame:
    non_intersection = catchment_area.overlay(regions_clipped, how='difference')
    if not non_intersection.empty:
        tide_query_location = get_non_intersection_centroid_position(catchment_area, non_intersection)
    else:
        coastline = get_nz_coastline_from_db(engine, catchment_area, distance_km)
        if not coastline.empty:
            coastline_geom = coastline['geometry'].iloc[0]
            boundary_centroids = get_catchment_boundary_centroids(catchment_area)
            boundary_centroids['dist_to_coast'] = boundary_centroids.distance(coastline_geom)
            tide_query_location = boundary_centroids.sort_values('dist_to_coast').head(1)
            tide_query_location = tide_query_location[['line_position', 'geometry']].rename(
                columns={'line_position': 'position'})
        else:
            raise NoTideDataException(
                f"No relevant tide data could be found within {distance_km}km of the catchment area. "
                f"As a result, tide data will not be used in the BG-Flood model.")
    tide_query_location = tide_query_location.to_crs(4326).reset_index(drop=True)
    return tide_query_location
