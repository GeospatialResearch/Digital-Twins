# -*- coding: utf-8 -*-
"""
Main river script used to read and store REC1 data in the database, fetch OSM waterways data, create a river network,
and generate the requested river model inputs for BG-Flood etc.
"""

import pathlib

import geopandas as gpd
from shapely.geometry import LineString
from sqlalchemy.engine import Engine

from src import config
from src.digitaltwin import setup_environment
from src.digitaltwin.utils import LogLevel, setup_logging, get_catchment_area
from src.dynamic_boundary_conditions.river.river_enum import BoundType
from src.dynamic_boundary_conditions.river import (
    river_data_to_from_db,
    river_network_for_aoi,
    river_inflows,
    hydrograph,
    river_model_input
)
from newzealidar.utils import get_dem_by_geometry


def get_hydro_dem_extent(engine: Engine, catchment_area: gpd.GeoDataFrame) -> LineString:
    """
    Get the extent of the Hydrologically Conditioned DEM.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.

    Returns
    -------
    LineString
        A LineString representing the extent of the Hydrologically Conditioned DEM.
    """
    # Retrieve DEM information by geometry
    _, _, raw_extent_path, _ = get_dem_by_geometry(engine, catchment_area)
    # Read the raw extent from the file
    raw_extent = gpd.read_file(raw_extent_path)
    # Create a GeoDataFrame containing the envelope of the raw extent
    hydro_dem_area = gpd.GeoDataFrame(geometry=[raw_extent.unary_union.envelope], crs=raw_extent.crs)
    # Get the exterior LineString from the GeoDataFrame
    hydro_dem_extent = hydro_dem_area.exterior.iloc[0]
    return hydro_dem_extent


def get_hydro_dem_boundary_lines(engine: Engine, catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Get the boundary lines of the Hydrologically Conditioned DEM.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the boundary lines of the Hydrologically Conditioned DEM.
    """
    # Obtain the spatial extent of the hydro DEM
    hydro_dem_extent = get_hydro_dem_extent(engine, catchment_area)
    # Create a list of LineString segments from the exterior boundary coordinates
    dem_boundary_lines_list = [
        LineString([hydro_dem_extent.coords[i], hydro_dem_extent.coords[i + 1]])
        for i in range(len(hydro_dem_extent.coords) - 1)
    ]
    # Generate numbers from 1 up to the total number of boundary lines
    dem_boundary_line_numbers = range(1, len(dem_boundary_lines_list) + 1)
    # Create a GeoDataFrame containing the boundary line numbers and LineString geometries
    dem_boundary_lines = gpd.GeoDataFrame(
        data={'dem_boundary_line_no': dem_boundary_line_numbers},
        geometry=dem_boundary_lines_list,
        crs=catchment_area.crs
    )
    # Rename the geometry column to 'dem_boundary_line'
    dem_boundary_lines = dem_boundary_lines.rename_geometry('dem_boundary_line')
    return dem_boundary_lines


def remove_existing_river_inputs(bg_flood_dir: pathlib.Path) -> None:
    """
    Remove existing river input files from the specified directory.

    Parameters
    ----------
    bg_flood_dir : pathlib.Path
        The BG-Flood model directory containing the river input files.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Iterate through all river input files in the directory
    for river_input_file in bg_flood_dir.glob('river[0-9]*.txt'):
        # Remove the file
        river_input_file.unlink()


def main(selected_polygon_gdf: gpd.GeoDataFrame, log_level: LogLevel = LogLevel.DEBUG) -> None:
    # Set up logging with the specified log level
    setup_logging(log_level)
    # Connect to the database
    engine = setup_environment.get_database()
    # Get catchment area
    catchment_area = get_catchment_area(selected_polygon_gdf, to_crs=2193)
    # BG-Flood Model Directory
    bg_flood_dir = config.get_env_variable("FLOOD_MODEL_DIR", cast_to=pathlib.Path)
    # Remove any existing river model inputs in the BG-Flood directory
    remove_existing_river_inputs(bg_flood_dir)

    # Store REC1 data to the database
    river_data_to_from_db.store_rec1_data_to_db(engine)
    # Get the REC1 river network for the catchment area
    rec1_network, rec1_network_data = river_network_for_aoi.get_rec1_river_network(engine, catchment_area)

    # Obtain REC1 river inflow data along with the corresponding river input points used in the BG-Flood model
    rec1_inflows_data = river_inflows.get_rec1_inflows_with_input_points(
        engine, catchment_area, rec1_network_data, distance_m=300)

    # Generate hydrograph data for the requested REC1 river inflow scenario
    hydrograph_data = hydrograph.get_hydrograph_data(
        rec1_inflows_data,
        flow_length_mins=2880,
        time_to_peak_mins=1440,
        maf=True,
        ari=None,
        bound=BoundType.MIDDLE)

    # # Generate river model inputs for BG-Flood
    # river_model_input.generate_river_model_input(bg_flood_dir, hydrograph_data)


if __name__ == "__main__":
    sample_polygon = gpd.GeoDataFrame.from_file("selected_polygon.geojson")
    main(sample_polygon)
