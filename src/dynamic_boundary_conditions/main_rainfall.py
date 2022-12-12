# -*- coding: utf-8 -*-
"""
@Script name: main.py
@Description:
@Author: pkh35
@Date: 17/01/2022
@Last modified by: sli229
@Last modified date: 8/12/2022
"""

import geopandas as gpd
import pathlib
from shapely.geometry import Polygon
from src.digitaltwin import setup_environment
from src.dynamic_boundary_conditions import rainfall_sites, thiessen_polygons, hyetograph, model_input
from src.dynamic_boundary_conditions import hirds_rainfall_data_to_db, hirds_rainfall_data_from_db


def catchment_area_geometry_info(catchment_file) -> Polygon:
    """
    Extract shapely geometry polygon from the catchment file.

    Parameters
    ----------
    catchment_file
        The file path of the catchment polygon shapefile.
    """
    catchment = gpd.read_file(catchment_file)
    catchment = catchment.to_crs(4326)
    catchment_polygon = catchment["geometry"][0]
    return catchment_polygon


def main():
    # Catchment polygon
    catchment_file = pathlib.Path(r"./selected_polygon.geojson")
    catchment_polygon = catchment_area_geometry_info(catchment_file)
    # Connect to the database
    engine = setup_environment.get_database()
    # Fetch rainfall sites data from the HIRDS website and store it to the database
    rainfall_sites.rainfall_sites_to_db(engine)
    # Calculate the area covered by each rainfall site across New Zealand and store it in the database
    nz_boundary_polygon = thiessen_polygons.get_new_zealand_boundary(engine)
    sites_in_nz = thiessen_polygons.get_sites_within_aoi(engine, nz_boundary_polygon)
    thiessen_polygons.thiessen_polygons_to_db(engine, nz_boundary_polygon, sites_in_nz)
    # Get all rainfall sites (thiessen polygons) coverage areas that are within the catchment area
    sites_in_catchment = thiessen_polygons.thiessen_polygons_from_db(engine, catchment_polygon)
    # Store rainfall data of all the sites within the catchment area in the database
    # Set idf to False for rain depth data and to True for rain intensity data
    hirds_rainfall_data_to_db.rainfall_data_to_db(engine, sites_in_catchment, idf=False)
    hirds_rainfall_data_to_db.rainfall_data_to_db(engine, sites_in_catchment, idf=True)
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

    # BG-Flood path
    bg_flood_path = pathlib.Path(r"U:/Research/FloodRiskResearch/DigitalTwin/BG-Flood/BG-Flood_Win10_v0.6-a")
    # Write out mean catchment rainfall data in a text file (used as spatially uniform rainfall input into BG-Flood)
    sites_coverage = model_input.sites_coverage_in_catchment(sites_in_catchment, catchment_polygon)
    mean_catchment_rain = model_input.mean_catchment_rainfall(hyetograph_data, sites_coverage)
    model_input.spatial_uniform_model_input(mean_catchment_rain, bg_flood_path)


if __name__ == "__main__":
    main()
