# -*- coding: utf-8 -*-
"""
@Script name: model_input.py
@Description:
@Author: sli229
@Date: 8/12/2022
"""

import pathlib
import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon
from src.digitaltwin import setup_environment
from src.dynamic_boundary_conditions import main_rainfall, thiessen_polygons, hirds_rainfall_data_from_db, hyetograph


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
    sites_coverage = sites_voronoi_intersect_catchment(sites_in_catchment, catchment_polygon)
    sites_coverage['area_in_km2'] = sites_coverage.to_crs(3857).area / 1e6
    sites_area_total = sites_coverage['area_in_km2'].sum()
    sites_area_percent = sites_coverage['area_in_km2'] / sites_area_total
    sites_coverage.insert(3, "area_percent", sites_area_percent)
    return sites_coverage


def spatial_uniform_method(hyetograph_data: pd.DataFrame, sites_coverage: gpd.GeoDataFrame) -> pd.DataFrame:
    increment_mins = hyetograph_data["mins"][1] - hyetograph_data["mins"][0]
    spatial_uniform_data = hyetograph_data.copy()
    sites_column_list = list(spatial_uniform_data.columns.values[:-3])
    for site_id in sites_column_list:
        site_area_percent = sites_coverage.query("site_id == @site_id")["area_percent"].values[0]
        spatial_uniform_data[f"{site_id}"] = spatial_uniform_data[f"{site_id}"] * site_area_percent
    spatial_uniform_data["rain_depth_mm"] = spatial_uniform_data[sites_column_list].sum(axis=1)
    spatial_uniform_data["rain_intensity_mmhr"] = spatial_uniform_data["rain_depth_mm"] / increment_mins * 60
    spatial_uniform_data = spatial_uniform_data[["mins", "hours", "seconds", "rain_depth_mm", "rain_intensity_mmhr"]]
    return spatial_uniform_data


def spatial_uniform_model_input(hyetograph_data: pd.DataFrame, sites_coverage: gpd.GeoDataFrame):
    spatial_uniform_data = spatial_uniform_method(hyetograph_data, sites_coverage)
    spatial_uniform_input = spatial_uniform_data[["seconds", "rain_intensity_mmhr"]]
    spatial_uniform_input.to_csv("U:/Research/FloodRiskResearch/DigitalTwin/BG-Flood/BG-Flood_Win10_v0.6-a/"
                                 "rain_forcing.txt",
                                 header=None, index=None, sep="\t")


def main():
    # Catchment polygon
    catchment_file = pathlib.Path(r"src\dynamic_boundary_conditions\catchment_polygon.shp")
    catchment_polygon = main_rainfall.catchment_area_geometry_info(catchment_file)
    # Connect to the database
    engine = setup_environment.get_database()
    # Get all rainfall sites (thiessen polygons) coverage areas that are within the catchment area
    sites_in_catchment = thiessen_polygons.thiessen_polygons_from_db(engine, catchment_polygon)

    # Requested scenario
    rcp = None  # 2.6
    time_period = None  # "2031-2050"
    ari = 50  # 100
    # For a requested scenario, get all rainfall data for sites within the catchment area from the database
    # Set idf to False for rain depth data and to True for rain intensity data
    rain_depth_in_catchment = hirds_rainfall_data_from_db.rainfall_data_from_db(
        engine, sites_in_catchment, rcp, time_period, ari, idf=False)
    # Get hyetograph data for all sites within the catchment area
    hyetograph_data = hyetograph.get_hyetograph_data(
        rain_depth_in_catchment,
        storm_length_hrs=48,
        time_to_peak_hrs=24,
        increment_mins=10,
        interp_method="cubic",
        hyeto_method="alt_block")
    # Create interactive hyetograph plots for sites within the catchment area
    hyetograph.hyetograph(hyetograph_data, ari)
    # Spatial uniform model input
    sites_coverage = sites_coverage_in_catchment(sites_in_catchment, catchment_polygon)
    spatial_uniform_model_input(hyetograph_data, sites_coverage)


if __name__ == "__main__":
    main()
