# -*- coding: utf-8 -*-
"""
@Description:
@Author: sli229
"""

import logging
import pathlib
from typing import Tuple

import pandas as pd
import sqlalchemy
from shapely.geometry import Polygon, Point, LineString

import geopandas as gpd
import geoapis.vector

from src import config
from src.digitaltwin import setup_environment

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def get_catchment_area(catchment_file: pathlib.Path) -> gpd.GeoDataFrame:
    catchment_area = gpd.read_file(catchment_file)
    catchment_area = catchment_area.to_crs(2193)
    return catchment_area


def get_stats_nz_dataset(key: str, layer_id: int) -> gpd.GeoDataFrame:
    vector_fetcher = geoapis.vector.StatsNz(key, verbose=True, crs=2193)
    response_data = vector_fetcher.run(layer_id)
    return response_data


def get_regional_council_clipped(key: str, layer_id: int) -> gpd.GeoDataFrame:
    regional_clipped = get_stats_nz_dataset(key, layer_id)
    regional_clipped.columns = regional_clipped.columns.str.lower()
    # move geometry column to last column
    regional_clipped = regional_clipped.drop(columns=['geometry'], axis=1).assign(geometry=regional_clipped['geometry'])
    regional_clipped = gpd.GeoDataFrame(regional_clipped)
    return regional_clipped


def check_table_exists(engine, db_table_name: str) -> bool:
    """
    Check if table exists in the database.

    Parameters
    ----------
    engine
        Engine used to connect to the database.
    db_table_name : str
        Database table name.
    """
    insp = sqlalchemy.inspect(engine)
    table_exists = insp.has_table(db_table_name, schema="public")
    return table_exists


def regional_council_clipped_to_db(engine, key: str, layer_id: int):
    if check_table_exists(engine, "region_geometry_clipped"):
        log.info("Table 'region_geometry_clipped' already exists in the database.")
    else:
        regional_clipped = get_regional_council_clipped(key, layer_id)
        regional_clipped.to_postgis("region_geometry_clipped", engine, index=False, if_exists="replace")
        log.info(f"Added regional council clipped (StatsNZ {layer_id}) data to database.")


def get_regions_clipped_from_db(engine, catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    catchment_polygon = catchment_area["geometry"][0]
    query = f"SELECT * FROM region_geometry_clipped AS rgc " \
            f"WHERE ST_Intersects(rgc.geometry, ST_GeomFromText('{catchment_polygon}', 2193))"
    regions_clipped = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry")
    return regions_clipped


def get_coastline_from_db(engine, catchment_area: gpd.GeoDataFrame, distance_km: int) -> gpd.GeoDataFrame:
    distance_m = distance_km * 1000
    catchment_area_buffered = catchment_area.buffer(distance=distance_m, join_style=2)
    area_of_interest = gpd.GeoDataFrame(geometry=catchment_area_buffered)
    aoi_polygon = area_of_interest["geometry"][0]
    query = f"SELECT * FROM \"_50258-nz-coastlines\" AS coast " \
            f"WHERE ST_Intersects(coast.geometry, ST_GeomFromText('{aoi_polygon}', 2193))"
    coastline = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry")
    return coastline


def get_catchment_boundary_lines(catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    catchment_polygon = catchment_area.geometry.iloc[0]
    # Extract the coordinates of the square polygon's exterior boundary
    boundary_coords = list(catchment_polygon.exterior.coords)
    # Create LineString objects for each boundary line
    top_line = LineString(boundary_coords[:2])
    right_line = LineString(boundary_coords[1:3])
    bottom_line = LineString(boundary_coords[2:4])
    left_line = LineString(boundary_coords[3:5])
    # Create a GeoDataFrame with the lines and their positions
    data = {
        'line_position': ['top', 'right', 'bottom', 'left'],
        'geometry': [top_line, right_line, bottom_line, left_line]
    }
    boundary_lines = gpd.GeoDataFrame(data, crs=2193)
    return boundary_lines


def get_catchment_boundary_centroids(catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    boundary_lines = get_catchment_boundary_lines(catchment_area)
    boundary_centroids = gpd.GeoDataFrame({
        'line_position': boundary_lines['line_position'],
        'geometry': boundary_lines.centroid})
    return boundary_centroids


def get_non_intersection_centroid_position(
        catchment_area: gpd.GeoDataFrame,
        non_intersection: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    boundary_lines = get_catchment_boundary_lines(catchment_area)
    non_intersection['centroid'] = non_intersection.centroid
    for index, row in non_intersection.iterrows():
        centroid = row['centroid']
        # Calculate the distance from the centroid to each line
        distances = {}
        for boundary_index, boundary_row in boundary_lines.iterrows():
            distances[boundary_row['line_position']] = centroid.distance(boundary_row['geometry'])
        # Find the name of the closest line based on the minimum distance
        closest_line = min(distances, key=distances.get)
        non_intersection.at[index, 'closest_line'] = closest_line
    return non_intersection


def get_tide_query_locations(
        engine,
        catchment_area: gpd.GeoDataFrame,
        regions_clipped: gpd.GeoDataFrame,
        distance_km: int = 1):
    non_intersection = catchment_area.overlay(regions_clipped, how='difference')
    if not non_intersection.empty:
        tide_query_location = get_non_intersection_centroid_position(catchment_area, non_intersection)
    else:
        coastline = get_coastline_from_db(engine, catchment_area, distance_km)
        if not coastline.empty:
            coastline_geom = coastline['geometry'].iloc[0]
            boundary_centroids = get_catchment_boundary_centroids(catchment_area)
            boundary_centroids['dist_to_coast'] = boundary_centroids.distance(coastline_geom)
            tide_query_location = boundary_centroids.sort_values('dist_to_coast').head(1)
        else:
            tide_query_location = gpd.GeoDataFrame()
            log.info("There are no relevant tide data for the catchment area.")
    return tide_query_location


def main():
    # Get StatsNZ api key
    stats_nz_api_key = config.get_env_variable("StatsNZ_API_KEY")
    # Connect to the database
    engine = setup_environment.get_database()
    # Catchment polygon
    catchment_file = pathlib.Path(r"selected_polygon.geojson")
    catchment_area = get_catchment_area(catchment_file)
    # Store regional council clipped data in the database
    regional_council_clipped_to_db(engine, stats_nz_api_key, 111181)
    regions_clipped = get_regions_clipped_from_db(engine, catchment_area)
    tide_query_location = get_tide_query_locations(engine, catchment_area, regions_clipped, distance_km=1)
    print(tide_query_location)


if __name__ == "__main__":
    main()
