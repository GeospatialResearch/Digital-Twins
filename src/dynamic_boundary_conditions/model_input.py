# -*- coding: utf-8 -*-
"""
@Description: Generate the requested rainfall model input for BG-Flood, i.e. spatially uniform rain input
              ('rain_forcing.txt' text file) or spatially varying rain input ('rain_forcing.nc' NetCDF file).
@Author: sli229
"""

import logging
import pathlib
import geopandas as gpd
import pandas as pd
import xarray as xr
from shapely.geometry import Polygon
from geocube.api.core import make_geocube

from src import config
from src.digitaltwin import setup_environment
from src.dynamic_boundary_conditions import main_rainfall, thiessen_polygons, hirds_rainfall_data_from_db, hyetograph
from src.dynamic_boundary_conditions.rainfall_enum import RainInputType, HyetoMethod

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
    Get the intersection of rainfall sites coverage areas (thiessen polygons) and the catchment area,
    i.e. return the overlapped areas (intersections).

    Parameters
    ----------
    sites_in_catchment : gpd.GeoDataFrame
        Rainfall sites coverage areas (thiessen polygons) that intersects or are within the catchment area.
    catchment_polygon : Polygon
        Desired catchment area.
    """
    catchment_area = gpd.GeoDataFrame(index=[0], crs='epsg:4326', geometry=[catchment_polygon])
    intersections = gpd.overlay(sites_in_catchment, catchment_area, how="intersection")
    return intersections


def sites_coverage_in_catchment(
        sites_in_catchment: gpd.GeoDataFrame,
        catchment_polygon: Polygon) -> gpd.GeoDataFrame:
    """
    Get the intersection of rainfall sites coverage areas (thiessen polygons) and the catchment area, and
    calculate the area and the percentage of area covered by each rainfall site inside the catchment area.

    Parameters
    ----------
    sites_in_catchment : gpd.GeoDataFrame
        Rainfall sites coverage areas (thiessen polygons) that intersects or are within the catchment area.
    catchment_polygon : Polygon
        Desired catchment area.
    """
    sites_coverage = sites_voronoi_intersect_catchment(sites_in_catchment, catchment_polygon)
    sites_coverage['area_in_km2'] = sites_coverage.to_crs(3857).area / 1e6
    sites_area_total = sites_coverage['area_in_km2'].sum()
    sites_area_percent = sites_coverage['area_in_km2'] / sites_area_total
    sites_coverage.insert(3, "area_percent", sites_area_percent)
    return sites_coverage


def mean_catchment_rainfall(hyetograph_data: pd.DataFrame, sites_coverage: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    Calculate the mean catchment rainfall intensities (weighted average of gauge measurements)
    across all durations using the thiessen polygon method.

    Parameters
    ----------
    hyetograph_data : pd.DataFrame
        Hyetograph intensities data for sites within the catchment area.
    sites_coverage : gpd.GeoDataFrame
        Contains the area and the percentage of area covered by each rainfall site inside the catchment area.
    """
    mean_catchment_rain = hyetograph_data.copy()
    sites_column_list = list(mean_catchment_rain.columns.values[:-3])
    for site_id in sites_column_list:
        site_area_percent = sites_coverage.query("site_id == @site_id")["area_percent"].values[0]
        mean_catchment_rain[f"{site_id}"] = mean_catchment_rain[f"{site_id}"] * site_area_percent
    mean_catchment_rain["rain_intensity_mmhr"] = mean_catchment_rain[sites_column_list].sum(axis=1)
    mean_catchment_rain = mean_catchment_rain[["mins", "hours", "seconds", "rain_intensity_mmhr"]]
    return mean_catchment_rain


def spatial_uniform_rain_input(
        hyetograph_data: pd.DataFrame,
        sites_coverage: gpd.GeoDataFrame,
        bg_flood_path: pathlib.Path):
    """
    Write the relevant mean catchment rainfall intensities data (i.e. 'seconds' and 'rain_intensity_mmhr' columns)
    in a text file (rain_forcing.txt). This can be used as spatially uniform rainfall input into the BG-Flood model.

    Parameters
    ----------
    hyetograph_data : pd.DataFrame
        Hyetograph intensities data for sites within the catchment area.
    sites_coverage : gpd.GeoDataFrame
        Contains the area and the percentage of area covered by each rainfall site inside the catchment area.
    bg_flood_path : pathlib.Path
        BG-Flood file path.
    """
    mean_catchment_rain = mean_catchment_rainfall(hyetograph_data, sites_coverage)
    spatial_uniform_input = mean_catchment_rain[["seconds", "rain_intensity_mmhr"]]
    spatial_uniform_input.to_csv(bg_flood_path / "rain_forcing.txt", header=None, index=None, sep="\t")


def create_rain_data_cube(hyetograph_data: pd.DataFrame, sites_coverage: gpd.GeoDataFrame) -> xr.Dataset:
    """
    Create rainfall intensities data cube (xarray data) for the catchment area across all durations,
    i.e. convert rainfall intensities vector data into rasterized xarray data.

    Parameters
    ----------
    hyetograph_data : pd.DataFrame
        Hyetograph intensities data for sites within the catchment area.
    sites_coverage : gpd.GeoDataFrame
        Contains the area and the percentage of area covered by each rainfall site inside the catchment area.
    """
    hyetograph_data_long = hyetograph.hyetograph_data_wide_to_long(hyetograph_data)
    hyetograph_data_long = hyetograph_data_long.merge(sites_coverage, how="inner")
    hyetograph_data_long.drop(columns=["site_name", "area_in_km2", "area_percent", "mins", "hours"], inplace=True)
    hyetograph_data_long.rename(columns={"seconds": "time"}, inplace=True)
    hyetograph_data_long = gpd.GeoDataFrame(hyetograph_data_long)

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
        bg_flood_path: pathlib.Path):
    """
    Write the rainfall intensities data cube out in NetCDF format (rain_forcing.nc).
    This can be used as spatially varying rainfall input into the BG-Flood model.

    Parameters
    ----------
    hyetograph_data : pd.DataFrame
        Hyetograph intensities data for sites within the catchment area.
    sites_coverage : gpd.GeoDataFrame
        Contains the area and the percentage of area covered by each rainfall site inside the catchment area.
    bg_flood_path : pathlib.Path
        BG-Flood file path.
    """
    rain_data_cube = create_rain_data_cube(hyetograph_data, sites_coverage)
    rain_data_cube.to_netcdf(bg_flood_path / "rain_forcing.nc")


def generate_rain_model_input(
        hyetograph_data: pd.DataFrame,
        sites_coverage: gpd.GeoDataFrame,
        bg_flood_path: pathlib.Path,
        input_type: RainInputType):
    """
    Generate the requested rainfall model input for BG-Flood, i.e. spatially uniform rain input ('rain_forcing.txt'
    text file) or spatially varying rain input ('rain_forcing.nc' NetCDF file).

    Parameters
    ----------
    hyetograph_data : pd.DataFrame
        Hyetograph data for sites within the catchment area.
    sites_coverage : gpd.GeoDataFrame
        Contains the area and the percentage of area covered by each rainfall site inside the catchment area.
    bg_flood_path : pathlib.Path
        BG-Flood file path.
    input_type: RainInputType
        Type of rainfall model input to be generated. One of 'uniform' or 'varying',
        i.e. spatially uniform rain input (text file) or spatially varying rain input (NetCDF file).
    """
    if input_type == RainInputType.UNIFORM:
        spatial_uniform_rain_input(hyetograph_data, sites_coverage, bg_flood_path)
        log.info(f"Successfully generated the spatially uniform rain input for BG-Flood. Located in: {bg_flood_path}")
    elif input_type == RainInputType.VARYING:
        spatial_varying_rain_input(hyetograph_data, sites_coverage, bg_flood_path)
        log.info(f"Successfully generated the spatially varying rain input for BG-Flood. Located in: {bg_flood_path}")


def main():
    # BG-Flood path
    flood_model_dir = config.get_env_variable("FLOOD_MODEL_DIR")
    bg_flood_path = pathlib.Path(flood_model_dir)
    # Catchment polygon
    catchment_file = pathlib.Path(r"selected_polygon.geojson")
    catchment_polygon = main_rainfall.catchment_area_geometry_info(catchment_file)
    # Connect to the database
    engine = setup_environment.get_database()
    # Get all rainfall sites (thiessen polygons) coverage areas that are within the catchment area
    sites_in_catchment = thiessen_polygons.thiessen_polygons_from_db(engine, catchment_polygon)
    # Requested scenario
    rcp = 2.6
    time_period = "2031-2050"
    ari = 100
    # For a requested scenario, get all rainfall data for sites within the catchment area from the database
    # Set idf to False for rain depth data and to True for rain intensity data
    rain_depth_in_catchment = hirds_rainfall_data_from_db.rainfall_data_from_db(
        engine, sites_in_catchment, rcp, time_period, ari, idf=False)
    # Get hyetograph data for all sites within the catchment area
    hyetograph_data = hyetograph.get_hyetograph_data(
        rain_depth_in_catchment,
        storm_length_mins=2880,
        time_to_peak_mins=1440,
        increment_mins=10,
        interp_method="cubic",
        hyeto_method=HyetoMethod.ALT_BLOCK)
    # Get the intersection of rainfall sites coverage areas (thiessen polygons) and the catchment area
    sites_coverage = sites_coverage_in_catchment(sites_in_catchment, catchment_polygon)
    # Write out the requested rainfall model input for BG-Flood
    generate_rain_model_input(hyetograph_data, sites_coverage, bg_flood_path, input_type=RainInputType.UNIFORM)
    generate_rain_model_input(hyetograph_data, sites_coverage, bg_flood_path, input_type=RainInputType.VARYING)


if __name__ == "__main__":
    main()
