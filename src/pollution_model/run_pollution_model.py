"""
This script takes in appropriate datasets as input and runs the MEDUSA2.0 model to calculate
TSS (total suspended solids), TCu (total copper), DCu  (dissolved copper), TZn (total zinc), and DZn (dissolved zinc).
"""

import logging
import math
import os
import pathlib
import platform
import subprocess
from datetime import datetime
from typing import Tuple, Union, Optional, TextIO
from enum import Enum

import geopandas as gpd
import numpy as np
import sqlalchemy
import xarray as xr
from newzealidar.utils import get_dem_by_geometry
from sqlalchemy import insert
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import text

from src import config
from src.digitaltwin import setup_environment
from src.digitaltwin.tables import BGFloodModelOutput, create_table, check_table_exists
from src.digitaltwin.utils import LogLevel, setup_logging, get_catchment_area
from src.flood_model.flooded_buildings import find_flooded_buildings
from src.flood_model.flooded_buildings import store_flooded_buildings_in_database
from src.flood_model.serve_model import add_model_output_to_geoserver

log = logging.getLogger(__name__)

Base = declarative_base()


class SurfaceType(Enum):
    ConcreteRoof = 1
    CopperRoof = 2
    GalvanisedRoof = 3
    AsphaltRoad = 4
    #CarPark = 5 - CarParks are classified the same as roads


def compute_tss_roof_road(surface_area,
                          antecedent_dry_days,
                          average_rain_intensity,
                          event_duration,
                          surface_type):
    """
    Calculates the total suspended solids (TSS) given the following parameters;

    Parameters
    ----------
    surface_area: float
        surface area of the given surface type
    antecedent_dry_days: float
        length of antecedent dry period (days)
    average_rain_intensity: float
        average rainfall intensity of the event (mm/h)
    event_duration: float
        duration of the rainfall event (h)
    surface_type: int
        the type of surface we are computing the TSS for

    Returns
    -------
    float
       Returns the TSS value from the given parameters
    """
    # Check to make sure we're working with a road or roof
    if surface_type <= 0 or surface_type > 4:
        log.error(
            f"Surface type Road or Roof expected for TSS calculation, but received {SurfaceType(surface_type).name}.")

    # Define the constants (Cf is the capacity factor).
    # Values a1 to a3 are empirically derived coefficient values.
    Cf = 0.25 if surface_type == 1 else 0.75
    a1, a2, a3 = 0, 0, 0

    first_term = surface_area * a1 * (antecedent_dry_days ** a2) * Cf
    second_term = (1 - math.exp(a3 * average_rain_intensity * event_duration))

    return first_term * second_term


def total_metal_load_roof(surface_area,
                          antecedent_dry_days,
                          average_rain_intensity,
                          event_duration,
                          rainfall_ph,
                          surface_type):
    """
    Calculates the total metal load for a given roof;

    Parameters
    ----------
    surface_area: float
        surface area of the given surface type
    antecedent_dry_days: float
        length of antecedent dry period (days)
    average_rain_intensity: float
        average rainfall intensity of the event (mm/h)
    event_duration: float
        duration of the rainfall event (h)
    rainfall_ph: float
        the acidity level of the rainfall
    surface_type: int
        the type of roof we are calculating the metal load for. Some coefficients depend on this.

    Returns
    -------
    (float, float)
       Returns the total copper and zinc loads from the given parameters (micrograms)
    """
    # Define constants in a list
    b = []
    c = []

    match surface_type:
        case 1:
            b = [2, -2.8, 0.5, 0.217, 3.57, -0.09, 7, -3.73]
            c = [50, 2600, 0.1, 0.01, 1, -3.1, -0.007, 0.056]
        case 2:
            b = [100, -2.8, 1.372, 0.217, 3.57, -1, 275, -3.3]
            c = [-0.1, 2, 0.1, 0.01, 0.8, -1.3, -0.007, 0.056]
        case 3:
            b = [2, -2.8, 0.5, 0.217, 3.57, -0.09, 7, -3.73]
            c = [910, 4, 0.2, 0.09, 1.5, -2, -0.23, 1.990]
        case _:
            log.error(
                f"Given surface type is not valid for computing total metal load. Needed a roof, but got {SurfaceType(surface_type).name}.")
    # Define the initial and second stage metal concentrations (X_0 and X_est)
    initial_copper_concentration = (b[0] * rainfall_ph ** b[1]) * (b[2] * antecedent_dry_days ** b[3]) * (
            b[4] * average_rain_intensity ** b[5])
    second_stage_copper = b[6] * rainfall_ph ** b[7]

    initial_zinc_concentration = (c[0] * rainfall_ph + c[1]) * (c[2] * antecedent_dry_days ** c[3]) * (
            c[4] * average_rain_intensity ** c[5])
    second_stage_zinc = c[6] * rainfall_ph + c[7]

    # Define Z as per experimental data
    z = 0.75

    # Define K, the wash off coefficient. TODO: find out what the k parameter should be
    k = 1

    # Initialise total copper and zinc loads as a guaranteed common factor
    total_copper_load = initial_copper_concentration * surface_area * (1 / k)
    total_zinc_load = initial_zinc_concentration * surface_area * (1 / k)

    # Calculate total metal loads, where the method depends on if Z is less than event_duration
    if event_duration <= z:
        factor = (1 - math.exp(k * average_rain_intensity * event_duration))
        total_zinc_load *= factor
        total_copper_load *= factor
    else:
        factor = (1 - math.exp(k * average_rain_intensity * z))
        bias_factor = average_rain_intensity * (event_duration - z)
        total_zinc_load = total_zinc_load * factor + second_stage_zinc * surface_area * bias_factor
        total_copper_load *= total_copper_load * factor + second_stage_copper * surface_area * bias_factor

    return total_copper_load, total_zinc_load


def total_metal_load_road_carpark(tss_surface):
    """
    Calculate the total metal load for car parks and roads from their total suspended solids.

    Parameters
    ----------
    tss_surface: float
        total suspended solids of this surface

    Returns
    -------
    float, float
       Returns the total copper and zinc loads for this surface
    """
    # Define constants
    d = 0.441
    e = 1.96
    # Return total copper load, total zinc load
    return tss_surface * d, tss_surface * e


def dissolved_metal_load(total_copper_load, total_zinc_load, surface_type):
    """
        Calculate the dissolved metal load for all surfaces from their total suspended solids.

        Parameters
        ----------
        total_copper_load: float
            total copper load for the surface
        total_zinc_load: float
            total zinc load for the surface
        surface_type: int
            The type of surface that we are calculating this for

        Returns
        -------
        float, float
           Returns the dissolved copper and zinc loads for this surface
        """
    # Declare constants
    f = 1
    g = 1
    # Set constant values based on surface type
    match surface_type:
        case 1:
            f = 0.46
            g = 0.67
        case 2:
            f = 0.77
            g = 0.72
        case 3:
            f = 0.28
            g = 0.43
        case 4:
            f = 0.28
            g = 0.43
        case _:
            log.error(
                f"Given surface type is not valid for computing dissolved metal load. {SurfaceType(surface_type).name}.")

    return f * total_copper_load, g * total_zinc_load


def get_building_information(engine: Engine):
    """
    Extracts relevant information about buildings from the database and formats them such that they are easy to use for
    pollution modeling purposes.

    Parameters
    ----------
    engine: Engine
      The sqlalchemy database connection engine

    Returns
    -------
    xr.DataArray
        A DataArray containing rows corresponding to buildings, and columns corresponding to
        attributes (Index, SurfaceArea, SurfaceType)
    """
    # Select all relevant information from the appropriate table
    # TODO: Update this when the database has been created
    query = text("SELECT building_id FROM nz_building_outlines")
    # Execute the SQL query
    result = engine.execute(query).fetchall()
    new_result = []
    for item in result:
        # TODO: Update this when the real database has been created
        # Append appropriate attribute data to the list. The attributes are Index, SurfaceArea, and SurfaceType.
        # Additionally, a placeholder for TSS, TCu, TZn, DCu, and DZn are included and set to "None". These will be
        # edited later.
        new_result.append([item[0], 1, 1, None, None, None, None, None])
    # Convert the list into a numpy array
    np_data = np.array(new_result)
    # Define the names of columns in the xarray
    col_names = ["Index", "SurfaceArea", "SurfaceType", "TSS", "TCu", "TZn", "DCu", "DZn"]
    # return the xarray containing the relevant data about buildings
    return xr.DataArray(new_result, dims=("row", "col"), coords={'row': range(np_data.shape[0]), 'col': col_names})


def get_road_information(engine: Engine):
    """
    Extracts relevant information about roads and car parks from the database and formats them such that they are easy
    to use for pollution modeling purposes.

    Parameters
    ----------
    engine: Engine
      The sqlalchemy database connection engine

    Returns
    -------
    xr.DataArray
        A DataArray containing rows corresponding to roads, and columns corresponding to
        attributes (Index, SurfaceArea, SurfaceType)
    """
    # Select all relevant information from the appropriate table
    # TODO: Update this when the database has been created -- Need to update the name of the table!
    query = text("SELECT road_id FROM nz_roads")
    # Execute the SQL query
    result = engine.execute(query).fetchall()
    new_result = []
    for item in result:
        # TODO: Update this when the real database has been created
        # Append appropriate attribute data to the list. The attributes are Index, SurfaceArea, and SurfaceType.
        # Additionally, a placeholder for TSS, TCu, TZn, DCu, and DZn are included and set to "None". These will be
        # edited later.
        new_result.append([item[0], 1, 1, None, None, None, None, None])
    # Convert the list into a numpy array
    np_data = np.array(new_result)
    # Define the names of columns in the xarray
    col_names = ["Index", "SurfaceArea", "SurfaceType", "TSS", "TCu", "TZn", "DCu", "DZn"]
    # return the xarray containing the relevant data about buildings
    return xr.DataArray(new_result, dims=("row", "col"), coords={'row': range(np_data.shape[0]), 'col': col_names})


def run_pollution_model_rain_event(
        engine: Engine,
        area_of_interest: gpd.GeoDataFrame,
        antecedent_dry_days: float,
        average_rain_intensity: float,
        event_duration: float,
        rainfall_ph: float) -> None:
    """
    Runs the pollution model for buildings (roofs), roads, and car parks. For each of these it calculates the TSS,
    total metal load, and dissolved metal load. This runs for one rain event.

    Parameters
    ----------
    engine: Engine
       The sqlalchemy database connection engine
    area_of_interest : gpd.GeoDataFrame
        A GeoDataFrame polygon specifying the area of interest to retrieve buildings in.
    antecedent_dry_days: float
        The number of dry days between rainfall events.
    average_rain_intensity: float
        The intensity of the rainfall event in mm/h.
    event_duration: float
        The number of hours of the rainfall event.
    rainfall_ph: float
        The pH level of the rainfall, a measure of acidity.

    Returns
    -------
    None
        This function does not return any value.
    """
    building_data = []
    # TODO: Get these values from a dataset
    all_buildings = get_building_information(engine)
    all_roads = get_road_information(engine)
    all_buildings.load()
    all_roads.load()

    print("START LOOPING...")
    # Run through each building and calculate TSS, total metal loads, and dissolved metal loads
    # TODO: change forloop to something meaningful. For the time being, it is simply a placeholder.
    for i in range(len(all_buildings)):
        surface_area = float(all_buildings.sel(row=i, col="SurfaceArea"))
        surface_type = int(all_buildings.sel(row=i, col="SurfaceType"))
        curr_tss = compute_tss_roof_road(surface_area=surface_area, antecedent_dry_days=antecedent_dry_days,
                                         average_rain_intensity=average_rain_intensity, event_duration=event_duration,
                                         surface_type=surface_type)

        curr_total_copper, curr_total_zinc = total_metal_load_roof(surface_area=surface_area,
                                                                   antecedent_dry_days=antecedent_dry_days,
                                                                   average_rain_intensity=average_rain_intensity,
                                                                   event_duration=event_duration,
                                                                   rainfall_ph=rainfall_ph, surface_type=surface_type)
        curr_dissolved_copper, curr_dissolved_zinc = dissolved_metal_load(total_copper_load=curr_total_copper,
                                                                          total_zinc_load=curr_total_zinc,
                                                                          surface_type=surface_type)
        all_buildings.loc[{'row': i}] = [all_buildings.loc[{'row': i}][0], surface_area, surface_type, curr_tss, curr_total_copper, curr_total_zinc, curr_dissolved_copper, curr_dissolved_zinc]
        # print(all_buildings.loc[{'row': i, 'col': "TSS"}])
        # all_buildings.loc[{'row': i, 'col': 'TSS'}] = curr_tss
        # all_buildings.loc[{'row': i, 'col': 'TCu'}] = curr_total_copper
        # all_buildings.loc[{'row': i, 'col': 'TZn'}] = curr_total_zinc
        # all_buildings.loc[{'row': i, 'col': 'DCu'}] = curr_dissolved_copper
        # all_buildings.loc[{'row': i, 'col': 'DZn'}] = curr_dissolved_zinc
    print(all_buildings)
    # Run through all the roads/car parks, and calculate TSS, total metal loads, and dissolved metal loads
    for i in range(len(all_roads)):
        surface_area = float(all_buildings.sel(row=i, col="SurfaceArea"))
        surface_type = int(all_buildings.sel(row=i, col="SurfaceType"))
        curr_tss = compute_tss_roof_road(surface_area=surface_area, antecedent_dry_days=antecedent_dry_days,
                                         average_rain_intensity=average_rain_intensity, event_duration=event_duration,
                                         surface_type=surface_type)

        curr_total_copper, curr_total_zinc = total_metal_load_road_carpark(curr_tss)
        curr_dissolved_copper, curr_dissolved_zinc = dissolved_metal_load(total_copper_load=curr_total_copper,
                                                                          total_zinc_load=curr_total_zinc,
                                                                          surface_type=surface_type)

        all_roads.loc[{'row': i, 'col': 'TSS'}] = curr_tss
        all_roads.loc[{'row': i, 'col': 'TCu'}] = curr_total_copper
        all_roads.loc[{'row': i, 'col': 'TZn'}] = curr_total_zinc
        all_roads.loc[{'row': i, 'col': 'DCu'}] = curr_dissolved_copper
        all_roads.loc[{'row': i, 'col': 'DZn'}] = curr_dissolved_zinc
    print(all_roads)

    all_result = xr.merge(all_roads, all_buildings)

def main(selected_polygon_gdf: gpd.GeoDataFrame,
         log_level: LogLevel = LogLevel.DEBUG,
         antecedent_dry_days: float = 1,
         average_rain_intensity: float = 1,
         event_duration: float = 1,
         rainfall_ph: float = 7):
    """
    Generate pollution model output for the requested catchment area, and incorporate the model output to GeoServer
    for visualization.

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
    antecedent_dry_days: float
        The number of dry days between rainfall events.
    average_rain_intensity: float
        The intensity of the rainfall event in mm/h.
    event_duration: float
        The number of hours of the rainfall event.
    rainfall_ph: float
        The pH level of the rainfall, a measure of acidity.

    Returns
    -------
    int
       Returns the model id of the new flood_model produced
    """
    # Set up logging with the specified log level
    setup_logging(log_level)
    # Connect to the database
    engine = setup_environment.get_database()
    # Get catchment area
    catchment_area = get_catchment_area(selected_polygon_gdf, to_crs=2193)

    # DEBUGGING:
    #print(get_building_information(engine).sel(row=0, col="Index"))

    # Run the pollution model
    run_pollution_model_rain_event(engine=engine, area_of_interest=catchment_area,
                                   antecedent_dry_days=antecedent_dry_days,
                                   average_rain_intensity=average_rain_intensity, event_duration=event_duration,
                                   rainfall_ph=rainfall_ph)
    return log_level


if __name__ == "__main__":
    sample_polygon = gpd.GeoDataFrame.from_file("selected_polygon.geojson")
    main(
        selected_polygon_gdf=sample_polygon,
        log_level=LogLevel.DEBUG,
        antecedent_dry_days=1,
        average_rain_intensity=1,
        event_duration=1,
        rainfall_ph=7
    )
