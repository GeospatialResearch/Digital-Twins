# -*- coding: utf-8 -*-
# Copyright © 2021-2025 Geospatial Research Institute Toi Hangarau
# LICENSE: https://github.com/GeospatialResearch/Digital-Twins/blob/master/LICENSE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
This script fetches LiDAR terrain data for a region of interest and creates a hydrologically-conditioned DEM.
It provides functions to retrieve information about the hydrologically-conditioned DEM and extract its boundary lines.
"""

import json
import logging
from typing import Tuple, Union

import geopandas as gpd
import newzealidar.datasets
import newzealidar.process
import pyproj
import xarray as xr
from newzealidar.utils import get_dem_band_and_resolution_by_geometry
from shapely import LineString
from shapely.geometry import box
from sqlalchemy.engine import Engine

from src.digitaltwin import setup_environment, tables
from src.digitaltwin.utils import LogLevel, setup_logging

log = logging.getLogger(__name__)


def retrieve_hydro_dem_info(
        engine: Engine,
        catchment_area: gpd.GeoDataFrame) -> Tuple[xr.Dataset, LineString, Union[int, float]]:
    """
    Retrieve the Hydrologically Conditioned DEM (Hydro DEM) data, along with its spatial extent and resolution,
    for the specified catchment area.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.

    Returns
    -------
    Tuple[xr.Dataset, LineString, Union[int, float]]
        A tuple containing the Hydro DEM data as a xarray Dataset, the spatial extent of the Hydro DEM as a LineString,
        and the resolution of the Hydro DEM as either an integer or a float.
    """
    # Retrieve the Hydro DEM data and resolution for the specified catchment area
    hydro_dem, res_no = get_dem_band_and_resolution_by_geometry(engine, catchment_area)
    # Extract the Coordinate Reference System (CRS) information from the 'hydro_dem' dataset
    hydro_dem_crs = pyproj.CRS(hydro_dem.spatial_ref.crs_wkt)
    # Get the bounding box (spatial extent) of the Hydro DEM and convert it to a GeoDataFrame
    hydro_dem_area = gpd.GeoDataFrame(geometry=[box(*hydro_dem.rio.bounds())], crs=hydro_dem_crs)
    # Get the exterior LineString from the GeoDataFrame
    hydro_dem_extent = hydro_dem_area.exterior.iloc[0]
    return hydro_dem, hydro_dem_extent, res_no


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
    _, hydro_dem_extent, _ = retrieve_hydro_dem_info(engine, catchment_area)
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


def ensure_lidar_datasets_initialised() -> None:
    """
    Check if LiDAR datasets table is initialised.
    This table holds URLs to data sources for LiDAR.
    If it is not initialised, then it initialises it by web-scraping OpenTopography which takes a long time.
    """
    # Connect to database
    engine = setup_environment.get_connection_from_profile()
    # Check if datasets table initialised
    if not tables.check_table_exists(engine, "dataset"):
        # If it is not initialised, then initialise it
        log.info("dataset table does not exist, initialising LiDAR dataset information.")
        newzealidar.datasets.main()
    # Check that datasets_mapping is in the instructions.json file
    instructions_file_name = "instructions.json"
    with open(instructions_file_name, "r", encoding="utf-8") as instructions_file:
        # Load content from the file
        instructions = json.load(instructions_file)["instructions"]
    dataset_mapping = instructions.get("dataset_mapping")
    # If the dataset_mapping does not exist on the instruction file then read it from the database
    if dataset_mapping is None:
        # Add dataset_mapping to instructions file, reading from database
        log.debug("instructions.json missing LiDAR dataset_mapping, filling from database.")
        newzealidar.utils.map_dataset_name(engine, instructions_file_name)


def process_dem(selected_polygon_gdf: gpd.GeoDataFrame) -> None:
    """
    Ensure hydrologically-conditioned DEM is processed for the given area and added to the database.

    Parameters
    ----------
    selected_polygon_gdf : gpd.GeoDataFrame
        The polygon defining the selected area to process the DEM for.
    """
    log.info("Processing LiDAR data into hydrologically conditioned DEM for area of interest.")
    newzealidar.process.main(selected_polygon_gdf)


def refresh_lidar_datasets() -> None:
    """
    Web-scrapes OpenTopography metadata to create the datasets table containing links to LiDAR data sources.
    Takes a long time to run but needs to be run periodically so that the datasets are up to date.
    """
    newzealidar.datasets.main()


def main(
        selected_polygon_gdf: gpd.GeoDataFrame,
        log_level: LogLevel = LogLevel.DEBUG) -> None:
    """
    Retrieve LiDAR data for the selected polygon and processes it into a hydrologically-conditioned DEM.

    Parameters
    ----------
    selected_polygon_gdf : gpd.GeoDataFrame
        A GeoDataFrame representing the selected polygon, i.e., the catchment area.
    log_level : LogLevel = LogLevel.DEBUG
        The log level to set for the root logger. Defaults to LogLevel.DEBUG.
        The available logging levels and their corresponding numeric values are:
        - LogLevel.CRITICAL (50)
        - LogLevel.ERROR (40)
        - LogLevel.WARNING (30)
        - LogLevel.INFO (20)
        - LogLevel.DEBUG (10)
        - LogLevel.NOTSET (0)
    """
    # Set up logging with the specified log level
    setup_logging(log_level)
    ensure_lidar_datasets_initialised()
    process_dem(selected_polygon_gdf)
