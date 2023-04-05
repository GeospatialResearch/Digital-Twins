# -*- coding: utf-8 -*-
"""
@Description:
@Author: sli229
"""

import logging
import pathlib

import pandas as pd
import sqlalchemy
from shapely.geometry import LineString, Point, box
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


def write_nz_bbox_to_file(engine, file_name: str = "nz_bbox.geojson"):
    file_path = pathlib.Path.cwd() / file_name
    if not file_path.is_file():
        query = "SELECT * FROM region_geometry"
        region_geom = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry")
        nz_geom = region_geom.tail(1).reset_index(drop=True)
        min_x, min_y, max_x, max_y = nz_geom.total_bounds
        bbox = box(min_x, min_y, max_x, max_y)
        nz_bbox = gpd.GeoDataFrame(geometry=[bbox], crs=2193)
        nz_bbox.to_file(file_name, driver="GeoJSON")


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


def get_catchment_boundary_info(catchment_area: gpd.GeoDataFrame) -> pd.DataFrame:
    # Get the exterior boundary of the catchment polygon
    boundary_lines = catchment_area["geometry"][0].exterior.coords
    # Create an empty dictionary to store boundary segment properties
    boundary_segments = {}
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
        # Add the boundary segment and its properties to the dictionary
        boundary_segments[i] = {'line_position': position, 'centroid': centroid, 'boundary': segment}
    # Convert the dictionary to a GeoDataFrame
    boundary_info = pd.DataFrame(boundary_segments).T
    return boundary_info


def get_catchment_boundary_lines(catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    boundary_info = get_catchment_boundary_info(catchment_area)
    boundary_lines = boundary_info[['line_position', 'boundary']].rename(columns={'boundary': 'geometry'})
    boundary_lines = boundary_lines.set_geometry('geometry', crs=2193)
    return boundary_lines


def get_catchment_boundary_centroids(catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    boundary_info = get_catchment_boundary_info(catchment_area)
    boundary_centroids = boundary_info[['line_position', 'centroid']].rename(columns={'centroid': 'geometry'})
    boundary_centroids = boundary_centroids.set_geometry('geometry', crs=2193)
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
        non_intersection.at[index, 'position'] = closest_line
    non_intersection = non_intersection[['position', 'centroid']].rename(columns={'centroid': 'geometry'})
    non_intersection = non_intersection.set_geometry('geometry')
    return non_intersection


def get_tide_query_locations(
        engine,
        catchment_area: gpd.GeoDataFrame,
        regions_clipped: gpd.GeoDataFrame,
        distance_km: int = 1) -> gpd.GeoDataFrame:
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
            tide_query_location = tide_query_location[['line_position', 'geometry']].rename(
                columns={'line_position': 'position'})
        else:
            log.info(f"No relevant tide data could be found within {distance_km}km of the catchment area. "
                     f"As a result, tide data will not be used in the BG-Flood model.")
            exit()
    tide_query_location = tide_query_location.reset_index(drop=True)
    return tide_query_location


def main():
    # Get StatsNZ api key
    stats_nz_api_key = config.get_env_variable("StatsNZ_API_KEY")
    # Connect to the database
    engine = setup_environment.get_database()
    write_nz_bbox_to_file(engine)
    # Catchment polygon
    catchment_file = pathlib.Path(r"selected_polygon.geojson")
    catchment_area = get_catchment_area(catchment_file)
    # Store regional council clipped data in the database
    regional_council_clipped_to_db(engine, stats_nz_api_key, 111181)
    # Get regions (clipped) that intersect with the catchment area from the database
    regions_clipped = get_regions_clipped_from_db(engine, catchment_area)
    # Get the location (coordinates) to fetch tide data for
    tide_query_loc = get_tide_query_locations(engine, catchment_area, regions_clipped, distance_km=1)
    print(tide_query_loc)


if __name__ == "__main__":
    main()
