"""
This script takes in appropriate datasets as input.
Then runs the MEDUSA2.0 model to calculate TSS (total suspended solids), TCu (total copper), DCu  (dissolved copper),
TZn (total zinc), and DZn (dissolved zinc).

DOI of the model paper: https://doi.org/10.3390/w12040969
"""

import logging
import math
from enum import StrEnum
from typing import Tuple

import geopandas as gpd
import pandas as pd
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base

from src.digitaltwin import setup_environment
from src.digitaltwin.tables import create_table
from src.digitaltwin.utils import LogLevel, setup_logging, get_catchment_area
from src.pollution_model.pollution_tables import MEDUSA2ModelOutput

log = logging.getLogger(__name__)

Base = declarative_base()


# Enum strings are assigned as they are described in the original paper
class SurfaceType(StrEnum):
    """
    StrEnum to represent the surface types that a feature could have.

    Attributes
    ----------
    CONCRETE_ROOF : str
        Concrete Roof surface.
    COPPER_ROOF : str
        Copper Roof surface.
    GALVANISED_ROOF : str
        Galvanised Roof surface.
    ASPHALT_ROAD : str
        Asphalt Road surface.
    CAR_PARK : str
        Car Park surface.
    """

    CONCRETE_ROOF = "Cr"
    COPPER_ROOF = "Cu"
    GALVANISED_ROOF = "Gv"
    ASPHALT_ROAD = "Rd"
    CAR_PARK = "CrP"  # CarParks are classified the same as roads


def compute_tss_roof_road(surface_area: float,
                          antecedent_dry_days: float,
                          average_rain_intensity: float,
                          event_duration: float,
                          surface_type: SurfaceType) -> float:
    """
    Calculate the total suspended solids (TSS) for a surface, given the following parameters.

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
    surface_type: SurfaceType
        the type of surface we are computing the TSS for

    Returns
    -------
    float
       Returns the TSS value from the given parameters

    Raises
    ----------
    ValueError
        If the surface type is not a roof or road (concrete, copper, galvanised roof, asphalt road, or car park).
    """
    # Define the constants (Cf is the capacity factor).
    roof_surface_types = {SurfaceType.CONCRETE_ROOF, SurfaceType.GALVANISED_ROOF, SurfaceType.COPPER_ROOF}
    capacity_factor = 0.75 if surface_type in roof_surface_types else 0.25
    # Values a1 to a3 are empirically derived coefficient values.

    # Define error message (if needed)
    invalid_surface_error = (f"Given surface is not valid for computing TSS."
                             f" Needed a roof or road, but got {SurfaceType(surface_type).name}.")

    a1, a2, a3 = 0, 0, 0
    match surface_type:
        case SurfaceType.CONCRETE_ROOF:
            a1, a2, a3 = 0.6, 0.25, 0.00933
        case SurfaceType.COPPER_ROOF:
            a1, a2, a3 = 2.5, 0.95, 0.00933
        case SurfaceType.GALVANISED_ROOF:
            a1, a2, a3 = 0.6, 0.5, 0.00933
        case SurfaceType.ASPHALT_ROAD | SurfaceType.CAR_PARK:
            a1, a2, a3 = 2.9, 0.16, 0.0008
        case _:
            raise ValueError(invalid_surface_error)
    first_term = surface_area * a1 * antecedent_dry_days ** a2 * capacity_factor
    second_term = 1 - math.exp(a3 * average_rain_intensity * event_duration)

    return first_term * second_term


def total_metal_load_roof(surface_area: float,
                          antecedent_dry_days: float,
                          average_rain_intensity: float,
                          event_duration: float,
                          rainfall_ph: float,
                          surface_type: SurfaceType) -> Tuple[float, float]:
    """
    Calculate the total metal load for a given roof.

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
    surface_type: SurfaceType
        the type of roof we are calculating the metal load for. Some coefficients depend on this.

    Returns
    -------
    Tuple[float, float]
       Returns the total copper and zinc loads from the given parameters (micrograms)

    Raises
    ----------
    ValueError
        If the surface type is not a roof (concrete, copper, or galvanised roof).
    """
    # Define error message (if needed)
    invalid_surface_error = (f"Given surface is not valid for computing total metal load."
                             f" Needed a roof, but got {SurfaceType(surface_type).name}.")
    # Define constants in a list

    match surface_type:
        case SurfaceType.CONCRETE_ROOF:
            b = [2, -2.8, 0.5, 0.217, 3.57, -0.09, 7, -3.73]
            c = [50, 2600, 0.1, 0.01, 1, -3.1, -0.007, 0.056]
        case SurfaceType.COPPER_ROOF:
            b = [100, -2.8, 1.372, 0.217, 3.57, -1, 275, -3.3]
            c = [-0.1, 2, 0.1, 0.01, 0.8, -1.3, -0.007, 0.056]
        case SurfaceType.GALVANISED_ROOF:
            b = [2, -2.8, 0.5, 0.217, 3.57, -0.09, 7, -3.73]
            c = [910, 4, 0.2, 0.09, 1.5, -2, -0.23, 1.990]
        case _:
            raise ValueError(invalid_surface_error)
    # Define the initial and second stage metal concentrations (X_0 and X_est)
    initial_copper_concentration = b[0] * rainfall_ph ** b[1] * b[2] * antecedent_dry_days ** b[3] * (
        b[4] * average_rain_intensity ** b[5])
    second_stage_copper = b[6] * rainfall_ph ** b[7]

    initial_zinc_concentration = c[0] * rainfall_ph + c[1] * c[2] * antecedent_dry_days ** c[3] * (
        c[4] * average_rain_intensity ** c[5])
    second_stage_zinc = c[6] * rainfall_ph + c[7]

    # Define Z as per experimental data
    z = 0.75

    # Define K, the wash off coefficient.
    k = 1

    # Initialise total copper and zinc loads as a guaranteed common factor
    total_copper_load = initial_copper_concentration * surface_area * 1 / k
    total_zinc_load = initial_zinc_concentration * surface_area * 1 / k

    # Calculate total metal loads, where the method depends on if Z is less than event_duration
    if event_duration <= z:
        factor = 1 - math.exp(k * average_rain_intensity * event_duration)
        total_zinc_load *= factor
        total_copper_load *= factor
    else:
        factor = 1 - math.exp(k * average_rain_intensity * z)
        bias_factor = average_rain_intensity * (event_duration - z)
        total_zinc_load = total_zinc_load * factor + second_stage_zinc * surface_area * bias_factor
        total_copper_load *= total_copper_load * factor + second_stage_copper * surface_area * bias_factor

    return total_copper_load, total_zinc_load


def total_metal_load_road_carpark(tss_surface: float) -> Tuple[float, float]:
    """
    Calculate the total metal load for a car park or road from their total suspended solids.

    Parameters
    ----------
    tss_surface: float
        total suspended solids of this surface

    Returns
    -------
    Tuple[float, float]
       Returns the total copper and zinc loads for this surface
       [Total Copper, Total Zinc]
    """
    # Define constants
    proportionality_constant_cu = 0.441
    proportionality_constant_zn = 1.96
    total_cu_load = tss_surface * proportionality_constant_cu
    total_zn_load = tss_surface * proportionality_constant_zn
    # Return total copper load, total zinc load
    return total_cu_load, total_zn_load


def dissolved_metal_load(total_copper_load: float, total_zinc_load: float,
                         surface_type: SurfaceType) -> Tuple[float, float]:
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
    Tuple[float, float]
        Returns the dissolved copper and zinc load for this surface
        [Dissolved Copper Load, Dissolved Zinc Load]

    Raises
    ----------
    ValueError
        If the surface type is not a roof or road (concrete, copper, galvanised roof, asphalt road, or car park).
    """
    # Define error message (if needed)
    invalid_surface_error = (f"Given surface is not valid for computing dissolved metal load."
                             f" Needed a roof or road, but got {SurfaceType(surface_type).name}.")
    # Set constant values based on surface type
    match surface_type:
        case SurfaceType.CONCRETE_ROOF:
            f = 0.46
            g = 0.67
        case SurfaceType.COPPER_ROOF:
            f = 0.77
            g = 0.72
        case SurfaceType.GALVANISED_ROOF:
            f = 0.28
            g = 0.43
        case SurfaceType.ASPHALT_ROAD | SurfaceType.CAR_PARK:
            f = 0.28
            g = 0.43
        case _:
            raise ValueError(invalid_surface_error)
    return f * total_copper_load, g * total_zinc_load


def get_building_information(_engine: Engine, _area_of_interest: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Extract relevant information about buildings from central_buildings.geojson, since the input data is not finalised.
    Then formats them such that they are easy to use for pollution modeling purposes.

    Github Issue to resolve the input_data: https://github.com/GeospatialResearch/Digital-Twins/issues/198

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing rows corresponding to buildings, and columns corresponding to
        attributes (Index, SurfaceArea, SurfaceType)
    """
    new_result = []

    buildings = gpd.GeoDataFrame.from_file("central_buildings.geojson")
    result = buildings
    for index, _ in result.iterrows():
        # Append appropriate attribute data to the list. The attributes are Index, SurfaceArea, and SurfaceType.
        # Additionally, a placeholder for TSS, TCu, TZn, DCu, and DZn are included and set to "None". These will be
        # edited later.
        surface_area = result.iloc[index]["geometry"].area
        new_result.append({"Index": index, "SurfaceArea": surface_area,
                           "SurfaceType": result.iloc[index]["surface_type"],
                           "TSS": None, "TCu": None, "TZn": None, "DCu": None, "DZn": None})

    # return the GeoDataFrame containing the relevant data about buildings
    return gpd.GeoDataFrame(new_result)


def get_road_information(engine: Engine, area_of_interest: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Extract relevant information about roads and car parks from the database.
    Then formats them such that they are easy to use for pollution modeling purposes.

    Parameters
    ----------
    engine: Engine
      The sqlalchemy database connection engine
    area_of_interest : gpd.GeoDataFrame
        A GeoDataFrame polygon specifying the area of interest to retrieve buildings in.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing rows corresponding to roads, and columns corresponding to
        attributes (Index, SurfaceArea, SurfaceType)
    """
    aoi_wkt = area_of_interest["geometry"][0].wkt
    crs = area_of_interest.crs.to_epsg()

    # Select all relevant information from the appropriate table
    query = f"""
    SELECT road_id, geometry FROM nz_roads
    WHERE ST_INTERSECTS(nz_roads.geometry, ST_GeomFromText('{aoi_wkt}', {crs}));
    """

    # Execute the SQL query
    result = gpd.GeoDataFrame.from_postgis(query, engine, index_col="road_id", geom_col="geometry")
    new_result = []

    for index, row in result.iterrows():
        # Append appropriate attribute data to the list. The attributes are Index, SurfaceArea, and SurfaceType.
        # Additionally, a placeholder for TSS, TCu, TZn, DCu, and DZn are included and set to "None". These will be
        # edited later.
        # Calculate surface area of roads. Currently, an approximation based on the length of the road * 5
        surface_area = row["geometry"].length * 5
        new_result.append({"Index": index, "SurfaceArea": surface_area, "SurfaceType": SurfaceType.ASPHALT_ROAD,
                           "TSS": None, "TCu": None, "TZn": None, "DCu": None, "DZn": None})

    # return the GeoDataFrame containing the relevant data about buildings
    return gpd.GeoDataFrame(new_result)


def run_pollution_model_rain_event(
        engine: Engine,
        area_of_interest: gpd.GeoDataFrame,
        antecedent_dry_days: float,
        average_rain_intensity: float,
        event_duration: float,
        rainfall_ph: float) -> gpd.GeoDataFrame:
    """
    Run the pollution model for buildings (roofs), roads, and car parks.
    For each of these it calculates the TSS, total metal load, and dissolved metal load. This runs for one rain event.

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
    gpd.GeoDataFrame
        The combined results of all buildings and roads from the MEDUSA2.0 pollution model
    """
    all_buildings = get_building_information(engine, area_of_interest)
    all_roads = get_road_information(engine, area_of_interest)

    # Run through each building and calculate TSS, total metal loads, and dissolved metal loads
    for index, row in all_buildings.iterrows():
        surface_area = float(row["SurfaceArea"])
        surface_type = row["SurfaceType"]
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
        all_buildings.loc[index] = [index, surface_area, surface_type, curr_tss,
                                    curr_total_copper, curr_total_zinc, curr_dissolved_copper, curr_dissolved_zinc]

    # Run through all the roads/car parks, and calculate TSS, total metal loads, and dissolved metal loads
    for i in range(len(all_roads)):
        surface_area = float(all_roads.iloc[i]["SurfaceArea"])
        surface_type = all_roads.iloc[i]["SurfaceType"]
        curr_tss = compute_tss_roof_road(surface_area=surface_area, antecedent_dry_days=antecedent_dry_days,
                                         average_rain_intensity=average_rain_intensity, event_duration=event_duration,
                                         surface_type=surface_type)

        curr_total_copper, curr_total_zinc = total_metal_load_road_carpark(curr_tss)
        curr_dissolved_copper, curr_dissolved_zinc = dissolved_metal_load(total_copper_load=curr_total_copper,
                                                                          total_zinc_load=curr_total_zinc,
                                                                          surface_type=surface_type)

        all_roads.iloc[i] = [all_roads.iloc[i]["Index"], surface_area, surface_type, curr_tss,
                             curr_total_copper, curr_total_zinc, curr_dissolved_copper, curr_dissolved_zinc]

    return gpd.GeoDataFrame(pd.concat([all_roads, all_buildings], ignore_index=True))


def store_pollution_model_in_database(engine: Engine, results: gpd.GeoDataFrame, scenario_id: int) -> None:
    """
    Append the details of the output of the MEDUSA 2.0 pollution model into the database, with an assigned scenario_id.

    Parameters
    ----------
    engine: Engine
        The sqlalchemy database connection engine
    results : gpd.GeoDataFrame
        GeoDataFrame containing a mapping of geospatial features (roads, roofs) to their MEDUSA2.0 outputs for the
        current model run
    scenario_id : int
        The id of the current medusa2.0 model run, to associate with the results.
    """
    results["scenario_id"] = scenario_id
    results.set_index("Index", inplace=True)
    results.to_sql("medusa2_model_output", engine, if_exists="append", index=True)


def get_next_scenario_id(engine: Engine) -> int:
    """
    Read the database to find the latest scenario id. Returns that id + 1 to give the new scenario_id.

    Parameters
    ----------
    engine: Engine
        The sqlalchemy database connection engine

    Returns
    -------
    int
        The scenario_id for the current output about to be appended to the database.
    """
    with engine.begin() as conn:
        result = conn.execute("SELECT MAX(scenario_id) FROM medusa2_model_output").fetchone()[0]
        max_scenario_id = result if result is not None else 0
        return max_scenario_id + 1


def main(selected_polygon_gdf: gpd.GeoDataFrame,
         log_level: LogLevel = LogLevel.DEBUG,
         antecedent_dry_days: float = 1,
         average_rain_intensity: float = 10000,
         event_duration: float = 5,
         rainfall_ph: float = 7) -> int:
    """
    Generate pollution model output for the requested catchment area, and save result to database.

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

    # Run the pollution model
    results = run_pollution_model_rain_event(engine=engine, area_of_interest=catchment_area,
                                             antecedent_dry_days=antecedent_dry_days,
                                             average_rain_intensity=average_rain_intensity,
                                             event_duration=event_duration,
                                             rainfall_ph=rainfall_ph)
    # Create the table medusa2_model_output in the database if it doesn't already exist
    create_table(engine, MEDUSA2ModelOutput)
    # Get the scenario ID for the current event
    scenario_id = get_next_scenario_id(engine)
    # Store the event information in a database
    store_pollution_model_in_database(engine=engine, results=results, scenario_id=scenario_id)
    return scenario_id


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
