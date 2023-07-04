# -*- coding: utf-8 -*-
"""
@Description: Generate the requested rainfall model input for BG-Flood, which can be either
              spatially uniform rain input ('rain_forcing.txt' text file) or
              spatially varying rain input ('rain_forcing.nc' NetCDF file).
@Author: sli229
"""

import logging
import pathlib

import geopandas as gpd
import pandas as pd
import xarray as xr
from shapely.geometry import Polygon
from geocube.api.core import make_geocube

from src.dynamic_boundary_conditions.rainfall_enum import RainInputType
from src.dynamic_boundary_conditions import main_rainfall, hyetograph

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def sites_voronoi_intersect_catchment(
        sites_in_catchment: gpd.GeoDataFrame,
        catchment_polygon: Polygon) -> gpd.GeoDataFrame:
    """
    Get the intersecting areas between the rainfall site coverage areas (Thiessen polygons) and the catchment area,
    i.e. return the overlapped areas.

    Parameters
    ----------
    sites_in_catchment : gpd.GeoDataFrame
        Rainfall site coverage areas (Thiessen polygons) that intersect or are within the catchment area.
    catchment_polygon : Polygon
        The polygon representing the catchment area.

    Returns
    -------
    gpd.GeoDataFrame
        GeoDataFrame containing the intersecting areas between the rainfall site coverage areas and the catchment area.
    """
    # Create a GeoDataFrame representing the catchment area
    catchment_area = gpd.GeoDataFrame(index=[0], crs=4326, geometry=[catchment_polygon])
    # Perform overlay operation to find the intersecting areas
    intersections = gpd.overlay(sites_in_catchment, catchment_area, how="intersection")
    return intersections


def sites_coverage_in_catchment(
        sites_in_catchment: gpd.GeoDataFrame,
        catchment_polygon: Polygon) -> gpd.GeoDataFrame:
    """
    Get the intersecting areas between the rainfall site coverage areas (Thiessen polygons) and the catchment area,
    and calculate the size and percentage of the area covered by each rainfall site inside the catchment area.

    Parameters
    ----------
    sites_in_catchment : gpd.GeoDataFrame
        Rainfall sites coverage areas (Thiessen polygons) that intersect or are within the catchment area.
    catchment_polygon : Polygon
        The polygon representing the catchment area.

    Returns
    -------
    gpd.GeoDataFrame
        GeoDataFrame containing the intersecting areas between the rainfall site coverage areas and the catchment area,
        with calculated size and percentage of area covered by each rainfall site.
    """
    # Get the intersecting areas between the rainfall site coverage areas and the catchment area
    sites_coverage = sites_voronoi_intersect_catchment(sites_in_catchment, catchment_polygon)
    # Calculate the size of each site's intersecting area in square kilometers
    sites_coverage['area_in_km2'] = sites_coverage.to_crs(3857).area / 1e6
    # Calculate the total area covered by all sites
    sites_area_total = sites_coverage['area_in_km2'].sum()
    # Calculate the percentage of area covered by each site
    sites_area_percent = sites_coverage['area_in_km2'] / sites_area_total
    # Insert the calculated area percentage into the GeoDataFrame
    sites_coverage.insert(3, "area_percent", sites_area_percent)
    return sites_coverage


def mean_catchment_rainfall(hyetograph_data: pd.DataFrame, sites_coverage: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    Calculate the mean catchment rainfall intensities (weighted average of gauge measurements)
    across all durations using the Thiessen polygon method.

    Parameters
    ----------
    hyetograph_data : pd.DataFrame
        Hyetograph intensities data for sites within the catchment area.
    sites_coverage : gpd.GeoDataFrame
        A GeoDataFrame containing information about the coverage area of each rainfall site within the catchment area,
        including the size and percentage of the catchment area covered by each site.

    Returns
    -------
    pd.DataFrame
        DataFrame containing the mean catchment rainfall intensities across all durations.
    """
    # Create a copy of the hyetograph data to store the mean catchment rainfall
    mean_catchment_rain = hyetograph_data.copy()
    # Get the list of rainfall site IDs
    sites_column_list = list(mean_catchment_rain.columns.values[:-3])

    for site_id in sites_column_list:
        # Get the coverage area percentage for the current site
        site_area_percent = sites_coverage.query("site_id == @site_id")["area_percent"].values[0]
        # Multiply the rainfall intensities of the current site by its coverage area percentage
        mean_catchment_rain[f"{site_id}"] = mean_catchment_rain[f"{site_id}"] * site_area_percent
    # Calculate the sum from all sites to obtain the mean catchment rainfall intensity
    mean_catchment_rain["rain_intensity_mmhr"] = mean_catchment_rain[sites_column_list].sum(axis=1)
    # Extract the relevant columns: time and the mean catchment rainfall intensity
    mean_catchment_rain = mean_catchment_rain[["mins", "hours", "seconds", "rain_intensity_mmhr"]]
    return mean_catchment_rain


def spatial_uniform_rain_input(
        hyetograph_data: pd.DataFrame,
        sites_coverage: gpd.GeoDataFrame,
        bg_flood_dir: pathlib.Path) -> None:
    """
    Write the mean catchment rainfall intensities data (i.e., 'seconds' and 'rain_intensity_mmhr' columns)
    into a text file named 'rain_forcing.txt'. This file can be used as spatially uniform rain input
    for the BG-Flood model.

    Parameters
    ----------
    hyetograph_data : pd.DataFrame
        Hyetograph intensities data for sites within the catchment area.
    sites_coverage : gpd.GeoDataFrame
        A GeoDataFrame containing information about the coverage area of each rainfall site within the catchment area,
        including the size and percentage of the catchment area covered by each site.
    bg_flood_dir : pathlib.Path
        BG-Flood model directory.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Calculate the mean catchment rainfall
    mean_catchment_rain = mean_catchment_rainfall(hyetograph_data, sites_coverage)
    # Select the relevant columns for spatially uniform rain input
    spatial_uniform_input = mean_catchment_rain[["seconds", "rain_intensity_mmhr"]]
    # Save the spatially uniform rain input data as a text file
    spatial_uniform_input.to_csv(bg_flood_dir / "rain_forcing.txt", header=None, index=None, sep="\t")


def create_rain_data_cube(hyetograph_data: pd.DataFrame, sites_coverage: gpd.GeoDataFrame) -> xr.Dataset:
    """
    Create rainfall intensities data cube (xarray data) for the catchment area across all durations,
    i.e. convert rainfall intensities vector data into rasterized xarray data.

    Parameters
    ----------
    hyetograph_data : pd.DataFrame
        Hyetograph intensities data for sites within the catchment area.
    sites_coverage : gpd.GeoDataFrame
        A GeoDataFrame containing information about the coverage area of each rainfall site within the catchment area,
        including the size and percentage of the catchment area covered by each site.

    Returns
    -------
    xr.Dataset
        Rainfall intensities data cube in the form of xarray dataset.
    """
    # Convert the wide hyetograph data to long format
    hyetograph_data_long = hyetograph.hyetograph_data_wide_to_long(hyetograph_data)
    # Merge hyetograph data with sites coverage information
    hyetograph_data_long = hyetograph_data_long.merge(sites_coverage, how="inner")
    # Drop unnecessary columns
    hyetograph_data_long.drop(columns=["site_name", "area_in_km2", "area_percent", "mins", "hours"], inplace=True)
    # Rename the 'seconds' column to 'time'
    hyetograph_data_long.rename(columns={"seconds": "time"}, inplace=True)
    # Convert to a GeoDataFrame
    hyetograph_data_long = gpd.GeoDataFrame(hyetograph_data_long)
    # Create the rainfall data cube
    rain_data_cube = make_geocube(
        vector_data=hyetograph_data_long,
        measurements=["rain_intensity_mmhr"],
        output_crs=2193,
        resolution=(-10, 10),
        group_by="time",
        fill=0)
    return rain_data_cube


def spatial_varying_rain_input(
        hyetograph_data: pd.DataFrame,
        sites_coverage: gpd.GeoDataFrame,
        bg_flood_dir: pathlib.Path) -> None:
    """
    Write the rainfall intensities data cube in NetCDF format (rain_forcing.nc).
    This file can be used as spatially varying rain input for the BG-Flood model.

    Parameters
    ----------
    hyetograph_data : pd.DataFrame
        Hyetograph intensities data for sites within the catchment area.
    sites_coverage : gpd.GeoDataFrame
        A GeoDataFrame containing information about the coverage area of each rainfall site within the catchment area,
        including the size and percentage of the catchment area covered by each site.
    bg_flood_dir : pathlib.Path
        BG-Flood model directory.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Create the rainfall data cube
    rain_data_cube = create_rain_data_cube(hyetograph_data, sites_coverage)
    # Save the rainfall data cube as a NetCDF file
    rain_data_cube.to_netcdf(bg_flood_dir / "rain_forcing.nc")


def generate_rain_model_input(
        hyetograph_data: pd.DataFrame,
        sites_coverage: gpd.GeoDataFrame,
        bg_flood_dir: pathlib.Path,
        input_type: RainInputType) -> None:
    """
    Generate the requested rainfall model input for BG-Flood, either spatially uniform rain input
    ('rain_forcing.txt' text file) or spatially varying rain input ('rain_forcing.nc' NetCDF file).

    Parameters
    ----------
    hyetograph_data : pd.DataFrame
        Hyetograph intensities data for sites within the catchment area.
    sites_coverage : gpd.GeoDataFrame
        A GeoDataFrame containing information about the coverage area of each rainfall site within the catchment area,
        including the size and percentage of the catchment area covered by each site.
    bg_flood_dir : pathlib.Path
        BG-Flood model directory.
    input_type: RainInputType
        The type of rainfall model input to be generated. Valid options are 'uniform' or 'varying',
        representing spatially uniform rain input (text file) or spatially varying rain input (NetCDF file).

    Returns
    -------
    None
        This function does not return any value.
    """
    # Remove any existing rainfall model inputs in the BG-Flood directory
    main_rainfall.remove_existing_rain_inputs(bg_flood_dir)
    # Generate the requested type of rainfall model input
    if input_type == RainInputType.UNIFORM:
        spatial_uniform_rain_input(hyetograph_data, sites_coverage, bg_flood_dir)
        log.info(f"Successfully generated the spatially uniform rain input for BG-Flood. Located in: {bg_flood_dir}")
    elif input_type == RainInputType.VARYING:
        spatial_varying_rain_input(hyetograph_data, sites_coverage, bg_flood_dir)
        log.info(f"Successfully generated the spatially varying rain input for BG-Flood. Located in: {bg_flood_dir}")
