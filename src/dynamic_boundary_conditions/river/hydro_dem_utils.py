"""
This script handles Hydrologically Conditioned Digital Elevation Model (Hydro DEM) data processing.
It provides functions to retrieve information about the Hydro DEM and extract its boundary lines.
"""

from typing import Union, Tuple

import geopandas as gpd
import pyproj
import xarray as xr
from newzealidar.utils import get_dem_band_and_resolution_by_geometry
from shapely.geometry import LineString
from shapely.geometry import box
from sqlalchemy.engine import Engine


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
    """  # noqa: D400
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
