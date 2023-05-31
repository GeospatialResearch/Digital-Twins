import logging
import pathlib
from typing import Union, Tuple

import geopandas as gpd
import pandas as pd
import numpy as np
import xarray as xr
import rioxarray as rxr
from shapely.geometry import Point

from src import config
from src.digitaltwin import setup_environment
from src.dynamic_boundary_conditions import main_river, river_data_to_from_db, river_network_for_aoi, osm_waterways

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def match_rec1_river_and_osm_waterway(
        rec1_network_data_on_bbox: gpd.GeoDataFrame,
        osm_waterways_data_on_bbox: gpd.GeoDataFrame,
        distance_threshold_m: int = 300) -> gpd.GeoDataFrame:
    rec1_network_on_bbox = rec1_network_data_on_bbox[
        ['objectid', 'boundary_point_centre', 'boundary_line', 'boundary_line_no']]
    osm_waterways_on_bbox = osm_waterways_data_on_bbox[
        ['id', 'boundary_point_centre', 'boundary_line', 'boundary_line_no']]
    match_rec1_and_osm = gpd.sjoin_nearest(
        rec1_network_on_bbox,
        osm_waterways_on_bbox,
        how='inner',
        distance_col="distances",
        max_distance=distance_threshold_m)
    if (match_rec1_and_osm['boundary_line_no_left'] == match_rec1_and_osm['boundary_line_no_right']).all():
        match_rec1_and_osm.drop(
            columns=['boundary_point_centre', 'boundary_line_left', 'boundary_line_no_left', 'index_right'],
            inplace=True)
        match_rec1_and_osm.rename(
            columns={'boundary_line_right': 'boundary_line', 'boundary_line_no_right': 'boundary_line_no'},
            inplace=True)
    # Sort the GeoDataFrame by 'distances' column in ascending order
    match_rec1_and_osm = match_rec1_and_osm.sort_values(by='distances')
    # Drop duplicated rows based on 'id' column, keeping the first occurrence (the closest distance)
    match_rec1_and_osm = match_rec1_and_osm.drop_duplicates(subset='id', keep='first')
    match_rec1_and_osm = match_rec1_and_osm.sort_values(by='boundary_line_no').reset_index(drop=True)
    match_rec1_and_osm = match_rec1_and_osm.set_geometry("boundary_line")
    return match_rec1_and_osm


def find_closest_osm_waterway(
        rec1_network_data_on_bbox: gpd.GeoDataFrame,
        osm_waterways_data_on_bbox: gpd.GeoDataFrame,
        distance_threshold_m: int = 300) -> gpd.GeoDataFrame:
    match_rec1_and_osm = match_rec1_river_and_osm_waterway(
        rec1_network_data_on_bbox, osm_waterways_data_on_bbox, distance_threshold_m)
    closest_osm_waterway = match_rec1_and_osm[['objectid', 'id']].merge(osm_waterways_data_on_bbox, on='id', how='left')
    closest_osm_waterway.drop(columns=['waterway'], inplace=True)
    closest_osm_waterway.rename(
        columns={
            'boundary_point': 'osm_boundary_point',
            'boundary_point_centre': 'osm_boundary_point_centre'},
        inplace=True)
    closest_osm_waterway = gpd.GeoDataFrame(closest_osm_waterway, geometry='osm_boundary_point_centre')
    return closest_osm_waterway


def get_hydro_dem_data() -> xr.Dataset:
    data_dir = config.get_env_variable("DATA_DIR")
    hydro_dem_file_path = pathlib.Path(data_dir) / "cache/results/generated_dem.nc"
    hydro_dem = rxr.open_rasterio(hydro_dem_file_path)
    hydro_dem = hydro_dem.sel(band=1)
    return hydro_dem


def get_hydro_dem_resolution() -> Tuple[xr.Dataset, Union[int, float]]:
    hydro_dem = get_hydro_dem_data()
    unique_resolutions = list(set(abs(res) for res in hydro_dem.rio.resolution()))
    res_no = unique_resolutions[0] if len(unique_resolutions) == 1 else None
    res_description = int(hydro_dem.description.split()[-1])
    if res_no != res_description:
        raise ValueError("Inconsistent resolution.")
    else:
        return hydro_dem, res_no


def get_osm_bound_point_in_dem(
        row_data: gpd.GeoDataFrame,
        clipped_dem: xr.Dataset) -> Tuple[int, int, Point]:
    x_coord = row_data['osm_boundary_point_centre'].iloc[0].x
    y_coord = row_data['osm_boundary_point_centre'].iloc[0].y
    midpoint_x_index = int(np.argmin(abs(clipped_dem['x'].values - x_coord)))
    midpoint_y_index = int(np.argmin(abs(clipped_dem['y'].values - y_coord)))
    midpoint_x = clipped_dem['x'].values[midpoint_x_index]
    midpoint_y = clipped_dem['y'].values[midpoint_y_index]
    midpoint_coord = Point(midpoint_x, midpoint_y)
    return midpoint_x_index, midpoint_y_index, midpoint_coord


def get_dem_coords_to_extract_elevation(
        clipped_dem: xr.Dataset,
        midpoint_x_index: int,
        midpoint_y_index: int) -> Tuple[np.ndarray, np.ndarray]:
    start_x_index = max(0, midpoint_x_index - 2)
    end_x_index = min(midpoint_x_index + 3, len(clipped_dem['x']))
    start_y_index = max(0, midpoint_y_index - 2)
    end_y_index = min(midpoint_y_index + 3, len(clipped_dem['y']))
    x_values = clipped_dem['x'].values[slice(start_x_index, end_x_index)]
    y_values = clipped_dem['y'].values[slice(start_y_index, end_y_index)]
    return x_values, y_values


def get_elevation_for_dem_coords(
        row_data: gpd.GeoDataFrame,
        clipped_dem: xr.Dataset,
        x_values: np.ndarray,
        y_values: np.ndarray) -> gpd.GeoDataFrame:
    z_elevation = clipped_dem.sel(x=x_values, y=y_values).to_dataframe().reset_index()
    z_elevation['target_point'] = z_elevation.apply(lambda row: Point(row['x'], row['y']), axis=1)
    z_elevation.drop(columns=['x', 'y', 'band', 'spatial_ref', 'source_class'], inplace=True)
    z_elevation = gpd.GeoDataFrame(z_elevation, geometry='target_point', crs=row_data.crs)
    return z_elevation


def get_min_elevation_dem_coord(
        z_elevation: gpd.GeoDataFrame,
        midpoint_coord: Point) -> gpd.GeoDataFrame:
    z_elevation['midpoint'] = midpoint_coord
    z_elevation['distance'] = z_elevation.apply(lambda row: row['midpoint'].distance(row['target_point']), axis=1)
    min_z_value = z_elevation['z'].min()
    min_z_rows = z_elevation[z_elevation['z'] == min_z_value]
    min_z_dem_coord = min_z_rows.sort_values('distance').head(1)
    min_z_dem_coord = min_z_dem_coord.drop(columns=['midpoint', 'distance']).reset_index(drop=True)
    return min_z_dem_coord


def get_target_points(
        closest_osm_waterway: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    hydro_dem, res_no = get_hydro_dem_resolution()
    closest_osm_waterway['boundary_line_buffered'] = (
        closest_osm_waterway['boundary_line'].buffer(distance=res_no, cap_style=2))
    target_points = gpd.GeoDataFrame()
    for i in range(len(closest_osm_waterway)):
        row_data = closest_osm_waterway.iloc[i:i + 1].reset_index(drop=True)
        clipped_dem = hydro_dem.rio.clip(row_data['boundary_line_buffered'])
        midpoint_x_index, midpoint_y_index, midpoint_coord = get_osm_bound_point_in_dem(row_data, clipped_dem)
        x_values, y_values = get_dem_coords_to_extract_elevation(clipped_dem, midpoint_x_index, midpoint_y_index)
        z_elevation = get_elevation_for_dem_coords(row_data, clipped_dem, x_values, y_values)
        min_z_dem_coord = get_min_elevation_dem_coord(z_elevation, midpoint_coord)
        merged_data = row_data.merge(min_z_dem_coord, how='left', left_index=True, right_index=True)
        target_points = pd.concat([target_points, merged_data])
    target_points['res_no'] = res_no
    target_points = target_points.set_geometry('target_point').reset_index(drop=True)
    return target_points


def get_matched_data_with_target_point(
        rec1_network_data_on_bbox: gpd.GeoDataFrame,
        osm_waterways_data_on_bbox: gpd.GeoDataFrame,
        distance_threshold_m: int = 300) -> gpd.GeoDataFrame:
    # Find the closest OSM waterways to REC1 river data
    closest_osm_waterway = find_closest_osm_waterway(
        rec1_network_data_on_bbox, osm_waterways_data_on_bbox, distance_threshold_m)
    target_points = get_target_points(closest_osm_waterway)
    matched_data = rec1_network_data_on_bbox.merge(target_points, on='objectid', how='right')
    matched_data.drop(columns=['boundary_line_no_x', 'boundary_line_x'], inplace=True)
    matched_data.rename(
        columns={
            'boundary_line_no_y': 'boundary_line_no',
            'boundary_line_y': 'boundary_line'},
        inplace=True)
    matched_data = matched_data.set_geometry("target_point")
    return matched_data
