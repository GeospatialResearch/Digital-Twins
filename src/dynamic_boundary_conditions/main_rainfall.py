# -*- coding: utf-8 -*-
"""
@Description:
@Author: pkh35, sli229
"""

import geopandas as gpd
import pathlib
from shapely.geometry import Polygon
from src.digitaltwin import setup_environment
from src.dynamic_boundary_conditions import rainfall_sites, thiessen_polygons, hyetograph, model_input
from src.dynamic_boundary_conditions import hirds_rainfall_data_to_db, hirds_rainfall_data_from_db
from src.dynamic_boundary_conditions.model_input import RainInputType


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
    # BG-Flood path
    bg_flood_path = pathlib.Path(r"U:/Research/FloodRiskResearch/DigitalTwin/BG-Flood/BG-Flood_Win10_v0.6-a")
    # Catchment polygon
    catchment_file = pathlib.Path(r"selected_polygon.geojson")
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
        storm_length_mins=2880,
        time_to_peak_mins=1440,
        increment_mins=10,
        interp_method="cubic",
        hyeto_method=hyetograph.HyetoMethod.ALT_BLOCK)
    # Create interactive hyetograph plots for sites within the catchment area
    hyetograph.hyetograph(hyetograph_data, ari)
    # Get the intersection of rainfall sites coverage areas (thiessen polygons) and the catchment area
    sites_coverage = model_input.sites_coverage_in_catchment(sites_in_catchment, catchment_polygon)
    # Write out the requested rainfall model input for BG-Flood
    model_input.generate_rain_model_input(
        hyetograph_data, sites_coverage, bg_flood_path, input_type=RainInputType.UNIFORM)
    model_input.generate_rain_model_input(
        hyetograph_data, sites_coverage, bg_flood_path, input_type=RainInputType.VARYING)


if __name__ == "__main__":
    main()
