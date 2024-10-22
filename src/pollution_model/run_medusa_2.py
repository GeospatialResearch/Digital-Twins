"""
This script takes in appropriate datasets as input.
Then runs the MEDUSA2.0 model to calculate TSS (total suspended solids), TCu (total copper), DCu  (dissolved copper),
TZn (total zinc), and DZn (dissolved zinc).

DOI of the model paper: https://doi.org/10.3390/w12040969
"""

import logging
import math
from enum import StrEnum
from typing import NamedTuple, Dict, Union, Optional
from xml.sax import saxutils

import geopandas as gpd
import pandas as pd
from sqlalchemy.engine import Engine
from sqlalchemy.sql import text
from tqdm import tqdm

from src import geoserver
from src.config import EnvVariable
from src.digitaltwin import setup_environment
from src.digitaltwin.tables import create_table, check_table_exists, execute_query
from src.digitaltwin.utils import get_catchment_area, LogLevel, setup_logging
from src.pollution_model.pollution_tables import Medusa2ModelOutputBuildings, Medusa2ModelOutputRoads
from src.pollution_model.pollution_tables import MedusaScenarios

log = logging.getLogger(__name__)


# Enum strings are assigned as they are described in the original paper
class SurfaceType(StrEnum):
    """
    StrEnum to represent the surface types that a feature could have.

    Attributes
    ----------
    COLOUR_STEEL : str
        Colour Steel surface
    GALVANISED : str
        Galvanised surface.
    METAL_OTHER : str
        Metal Other surface.
    METAL_TILE : str
        Metal Tile surface.
    NON_METAL : str
        Non-Metal surface.
    ZINCALUME : str
        Zincalume surface.
    ASPHALT_ROAD: str
        Asphalt Road.
    CAR_PARK : str
        Car park.
    """

    COLOUR_STEEL = "ColourSteel"
    GALVANISED = "Galvanised"
    METAL_OTHER = "MetalOther"
    METAL_TILE = "MetalTile"
    NON_METAL = "NonMetal"
    ZINCALUME = "Zincalume"
    ASPHALT_ROAD = "AsphaltRoad"
    CAR_PARK = "CarPark"  # CarParks are classified the same as roads


ROOF_SURFACE_TYPES = {SurfaceType.COLOUR_STEEL, SurfaceType.GALVANISED, SurfaceType.METAL_OTHER, SurfaceType.METAL_TILE,
                      SurfaceType.NON_METAL, SurfaceType.ZINCALUME}
ROAD_SURFACE_TYPES = {SurfaceType.ASPHALT_ROAD, SurfaceType.CAR_PARK}


class MedusaRainfallEvent(NamedTuple):
    """
    Rainfall event parameters for MEDUSA 2.0 model.

    Attributes
    ----------
    antecedent_dry_days: float
        Length of antecedent dry period (days).
    average_rain_intensity: float
        Average rainfall intensity of the event (mm/h).
    event_duration: float
        Duration of the rainfall event (h).
    rainfall_ph: float
        The acidity level of the rainfall.
    """

    antecedent_dry_days: float
    average_rain_intensity: float
    event_duration: float
    rainfall_ph: float

    def as_dict(self) -> Dict[str, float]:
        """
        Convert the MedusaRainfallEvent parameters to a dictionary.

        Returns
        -------
        Dict[str, float]
            Returns the MedusaRainfallEvent parameters as a dictionary.
        """
        # NamedTuple has a documented _asdict method, that is hidden only to prevent conflicts.
        return self._asdict()  # pylint: disable=no-member


class MetalLoads(NamedTuple):
    """
    Contributing metal load results for the pollutant model.

    Attributes
    ----------
    cu_load: float
        Amount of copper load contributed by a step in the pollutant model (micrograms).
    zn_load: float
        Amount of zinc load contributed by a step in the pollutant model (micrograms).
    """

    cu_load: float
    zn_load: float


def compute_tss_roof_road(surface_area: float,
                          rainfall_event: MedusaRainfallEvent,
                          surface_type: SurfaceType) -> float:
    """
    Calculate the total suspended solids (TSS) for a surface, given the following parameters.

    Parameters
    ----------
    surface_area: float
        surface area of the given surface type
    rainfall_event: MedusaRainfallEvent
        Rainfall event parameters for MEDUSA 2.0 model.
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
    capacity_factor = 0.75 if surface_type in ROOF_SURFACE_TYPES else 0.25
    # Values a1 to a3 are empirically derived coefficient values.

    # Define error message (if needed)
    invalid_surface_error = (f"Given surface is not valid for computing TSS."
                             f" Needed a roof or road, but got {SurfaceType(surface_type).name}.")

    match surface_type:
        case SurfaceType.COLOUR_STEEL:
            a1, a2, a3 = 0.4, 0.5, 0.008
        case SurfaceType.GALVANISED:
            a1, a2, a3 = 0.4, 0.5, 0.008
        case SurfaceType.METAL_OTHER:
            # Using coefficients of Galvanised rather than Copper
            a1, a2, a3 = 0.4, 0.5, 0.008
        case SurfaceType.METAL_TILE:
            a1, a2, a3 = 0.4, 0.5, 0.008
        case SurfaceType.NON_METAL:
            a1, a2, a3 = 0.6, 0.25, 0.008
        case SurfaceType.ZINCALUME:
            a1, a2, a3 = 0.4, 0.5, 0.008
        case SurfaceType.ASPHALT_ROAD | SurfaceType.CAR_PARK:
            a1, a2, a3 = 190, 0.16, 0.0125
        case _:
            raise ValueError(invalid_surface_error)
    antecedent_dry_days, average_rain_intensity, event_duration, _ph = rainfall_event
    first_term = surface_area * a1 * antecedent_dry_days ** a2 * capacity_factor
    second_term = 1 - math.exp(a3 * average_rain_intensity * event_duration)

    return first_term * second_term


def total_metal_load_surface(surface_area: float,
                             rainfall_event: MedusaRainfallEvent,
                             surface_type: SurfaceType,
                             tss_surface: float) -> MetalLoads:
    """
    Calculate the total metal load for a given surface. Works for roofs, carparks, and roads.

    Parameters
    ----------
    surface_area: float
        Surface area of the given surface type.
    rainfall_event: MedusaRainfallEvent
        Rainfall event parameters for MEDUSA 2.0 model.
    surface_type: SurfaceType
        The type of surface we are calculating the metal load for. Some coefficients depend on this.
    tss_surface: float
        The amount of total suspended solids (TSS) the surface is contributing from the rainfall event.

    Returns
    -------
    MetalLoads
       Returns the total copper and zinc loads from the given parameters (micrograms).

    Raises
    ----------
    ValueError
        If the surface type is not a valid roof or road type.
    """
    if surface_type in ROOF_SURFACE_TYPES:
        return total_metal_load_roof(surface_area, rainfall_event, surface_type)
    if surface_type in ROAD_SURFACE_TYPES:
        return total_metal_load_road_carpark(tss_surface)
    raise ValueError(f"{surface_type} is not a valid roof or road type.")


def total_metal_load_roof(surface_area: float,
                          rainfall_event: MedusaRainfallEvent,
                          surface_type: SurfaceType) -> MetalLoads:
    """
    Calculate the total metal load for a given roof.

    Parameters
    ----------
    surface_area: float
        surface area of the given surface type
    rainfall_event: MedusaRainfallEvent
        Rainfall event parameters for MEDUSA 2.0 model.
    surface_type: SurfaceType
        the type of roof we are calculating the metal load for. Some coefficients depend on this.

    Returns
    -------
    MetalLoads
       Returns the total copper and zinc loads from the given parameters (micrograms).

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
        case SurfaceType.COLOUR_STEEL:
            b = [2, -2.802, 0.5, 0.217, 3.57, -0.09, 7, -3.732]
            c = [910, 4, 0.2, 0.09, 1.5, -2, -0.23, 1.99]
            # Roof wash off coefficient (based on rate of decay to second concentrations from initial ones)
            k = 0.00933
            # Duration of the event measured by hours - Roof
            # observed from the intra-event concentration sampling
            z = 0.75
        case SurfaceType.GALVANISED:
            b = [2, -2.802, 0.5, 0.217, 3.57, -0.09, 7, -3.732]
            c = [910, 4, 0.2, 0.09, 1.5, -2, -0.23, 1.99]
            # Roof wash off coefficient (based on rate of decay to second concentrations from initial ones)
            k = 0.00933
            # Duration of the event measured by hours - Roof
            # observed from the intra-event concentration sampling
            z = 0.75
        case SurfaceType.METAL_OTHER:
            # Using coefficients of Galvanised rather than Copper
            b = [2, -2.802, 0.5, 0.217, 3.57, -0.09, 7, -3.732]
            c = [910, 4, 0.2, 0.09, 1.5, -2, -0.23, 1.99]
            # Roof wash off coefficient (based on rate of decay to second concentrations from initial ones)
            k = 0.00933
            # Duration of the event measured by hours - Roof
            # observed from the intra-event concentration sampling
            z = 0.75
        case SurfaceType.METAL_TILE:
            b = [2, -2.802, 0.5, 0.217, 3.57, -0.09, 7, -3.732]
            c = [910, 4, 0.2, 0.09, 1.5, -2, -0.23, 1.99]
            # Roof wash off coefficient (based on rate of decay to second concentrations from initial ones)
            k = 0.00933
            # Duration of the event measured by hours - Roof
            # observed from the intra-event concentration sampling
            z = 0.75
        case SurfaceType.NON_METAL:
            b = [2, -2.802, 0.5, 0.217, 3.57, -0.09, 7, -3.732]
            c = [50, 2600, 0.1, 0.01, 1, -3.1, -0.007, 0.056]
            # Roof wash off coefficient (based on rate of decay to second concentrations from initial ones)
            k = 0.00933
            # Duration of the event measured by hours - Roof
            # observed from the intra-event concentration sampling
            z = 0.75
        case SurfaceType.ZINCALUME:
            b = [2, -2.802, 0.5, 0.217, 3.57, -0.09, 7, -3.732]
            c = [910, 4, 0.2, 0.09, 1.5, -2, -0.23, 1.99]
            # Roof wash off coefficient (based on rate of decay to second concentrations from initial ones)
            k = 0.00933
            # Duration of the event measured by hours - Roof
            # observed from the intra-event concentration sampling
            z = 0.75
        case _:
            raise ValueError(invalid_surface_error)

    antecedent_dry_days, average_rain_intensity, event_duration, rainfall_ph = rainfall_event
    # Define the initial and second stage metal concentrations (X_0 and X_est)
    initial_copper_concentration = b[0] * rainfall_ph ** b[1] * b[2] * antecedent_dry_days ** b[3] * (
        b[4] * average_rain_intensity ** b[5])
    second_stage_copper = b[6] * rainfall_ph ** b[7]

    initial_zinc_concentration = c[0] * rainfall_ph + c[1] * c[2] * antecedent_dry_days ** c[3] * (
        c[4] * average_rain_intensity ** c[5])
    second_stage_zinc = c[6] * rainfall_ph + c[7]

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

    return MetalLoads(total_copper_load, total_zinc_load)


def total_metal_load_road_carpark(tss_surface: float) -> MetalLoads:
    """
    Calculate the total metal load for a car park or road from their total suspended solids.

    Parameters
    ----------
    tss_surface: float
        total suspended solids of this surface

    Returns
    -------
    MetalLoads
       Returns the total copper and zinc loads for this surface (micrograms)
       [Total Copper, Total Zinc]
    """
    # Define constants
    proportionality_constant_cu = 0.441
    proportionality_constant_zn = 1.96
    total_cu_load = tss_surface * proportionality_constant_cu
    total_zn_load = tss_surface * proportionality_constant_zn
    # Return total copper load, total zinc load
    return MetalLoads(total_cu_load, total_zn_load)


def dissolved_metal_load(total_copper_load: float, total_zinc_load: float,
                         surface_type: SurfaceType) -> MetalLoads:
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
    MetalLoads
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
        case SurfaceType.COLOUR_STEEL:
            f = 0.5
            g = 0.43
        case SurfaceType.GALVANISED:
            f = 0.5
            g = 0.43
        case SurfaceType.METAL_OTHER:
            f = 0.5
            g = 0.43
        case SurfaceType.METAL_TILE:
            f = 0.5
            g = 0.43
        case SurfaceType.NON_METAL:
            f = 0.77
            g = 0.67
        case SurfaceType.ZINCALUME:
            f = 0.5
            g = 0.43
        case SurfaceType.ASPHALT_ROAD | SurfaceType.CAR_PARK:
            f = 0.28
            g = 0.43
        case _:
            raise ValueError(invalid_surface_error)
    return MetalLoads(f * total_copper_load, g * total_zinc_load)


def save_roof_surface_type_points_to_db(engine: Engine) -> None:
    """
    Read building data under points. Then store them into database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    """
    # Check if the table already exist in the database
    if check_table_exists(engine, "roof_surface_points"):
        log.info("roof_surface_points data already exists in the database.")
    else:
        # Read roof surface points from outside
        # This data has the deeplearn_matclass with roof types we need
        log.info(f"Reading roof surface points from {EnvVariable.ROOF_SURFACE_DATASET_PATH}.")
        roof_surface_points = gpd.read_file(EnvVariable.ROOF_SURFACE_DATASET_PATH,
                                            layer="CCC_Lynker_RoofMaterial_Update_2023")
        # Remove rows of building_Id and deeplearn_subclass that are NANs
        roof_surface_points = roof_surface_points.dropna(subset=['building_Id', 'deeplearn_subclass'])
        # Store the building_point_data to the database table
        log.info("Adding roof_surface_points table to the database.")
        roof_surface_points.to_postgis("roof_surface_points", engine, index=False, if_exists="replace")


def save_roof_surface_polygons_to_db(engine: Engine) -> None:
    """
    Read building data under points. Then store them into database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    """
    # Check if the table already exist in the database
    if check_table_exists(engine, "roof_surface_polygons"):
        log.info("roof_surface_polygons data already exists in the database.")
    else:
        # Read roof surface polygons from outside
        log.info(f"Reading roof surface polygons file {EnvVariable.ROOF_SURFACE_DATASET_PATH}.")
        roof_surface_polygons = gpd.read_file(EnvVariable.ROOF_SURFACE_DATASET_PATH, layer="BuildingPolygons")
        # Store the building_point_data to the database table
        log.info("Adding roof_surface_polygons table to the database.")
        roof_surface_polygons.to_postgis("roof_surface_polygons", engine, index=False, if_exists="replace")


def get_building_information(engine: Engine, area_of_interest: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Extract relevant information about buildings from central_buildings.geojson, since the input data is not finalised.
    Then formats them such that they are easy to use for pollution modeling purposes.

    Parameters
    ----------
    engine: Engine
        The sqlalchemy database connection engine.
    area_of_interest : gpd.GeoDataFrame
        A GeoDataFrame polygon specifying the area of interest to retrieve buildings in.


    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing rows corresponding to buildings, and columns corresponding to
        attributes (Index, SurfaceArea, SurfaceType)
    """
    # Add roof surface polygons to database
    save_roof_surface_polygons_to_db(engine)
    # Add roof surface type points to database.
    save_roof_surface_type_points_to_db(engine)

    # Convert current area of interest format into the format can be used by SQL
    aoi_wkt = area_of_interest["geometry"][0].wkt
    crs = area_of_interest.crs.to_epsg()

    # Select all relevant information from the appropriate table
    query = text("""
        SELECT
            polygons."building_Id",
            points.deeplearn_subclass AS surface_type,
            polygons.geometry
        FROM roof_surface_polygons AS polygons
            INNER JOIN roof_surface_points AS points
        USING ("building_Id")
        WHERE ST_INTERSECTS(points.geometry, ST_GeomFromText(:aoi_wkt, :crs))
    """).bindparams(aoi_wkt=str(aoi_wkt), crs=str(crs))

    # Execute the SQL query
    buildings = gpd.GeoDataFrame.from_postgis(query, engine, index_col="building_Id", geom_col="geometry")
    return buildings


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
    query = text("""
    SELECT road_id, geometry FROM nz_roads
    WHERE ST_INTERSECTS(nz_roads.geometry, ST_GeomFromText(:aoi_wkt, :crs));
    """).bindparams(aoi_wkt=str(aoi_wkt), crs=str(crs))

    # Execute the SQL query
    roads = gpd.GeoDataFrame.from_postgis(query, engine, index_col="road_id", geom_col="geometry")

    # Filter columns that are useful for MEDUSA model
    roads_medusa_info = roads[["geometry"]]
    # There is only one SurfaceType for roads.
    roads_medusa_info["surface_type"] = SurfaceType.ASPHALT_ROAD
    # Append columns specific to MEDUSA, to be filled later in the processing.
    roads_medusa_info[
        ["total_suspended_solids", "total_copper", "total_zinc", "dissolved_copper", "dissolved_zinc"]] = None

    # return the GeoDataFrame containing the relevant data about roads
    return gpd.GeoDataFrame(roads_medusa_info)


def run_medusa_model_for_single_surface(row: gpd.GeoSeries, rainfall_event: MedusaRainfallEvent) -> gpd.GeoSeries:
    """
    Run the pollution model for one surface geometry.
    Calculate the TSS, total metal load, and dissolved metal load and add to the surface. This runs for one rain event.

    Parameters
    ----------
    row: gpd.GeoSeries
        A Polygon containing the surface's geometry with surface type info to run MEDUSA model on.
    rainfall_event: MedusaRainfallEvent
        Rainfall event parameters for MEDUSA model.

    Returns
    -------
    gpd.GeoDataFrame
        The MEDUSA results for the given surfaces and rainfall_event.
    """
    surface_type = row["surface_type"]
    if surface_type == SurfaceType.ASPHALT_ROAD:
        surface_area = row.geometry.length * 5
    else:
        surface_area = row.geometry.area

    curr_tss = compute_tss_roof_road(surface_area, rainfall_event, surface_type)

    curr_total_copper, curr_total_zinc = total_metal_load_surface(surface_area,
                                                                  rainfall_event,
                                                                  surface_type,
                                                                  curr_tss)

    curr_dissolved_copper, curr_dissolved_zinc = dissolved_metal_load(total_copper_load=curr_total_copper,
                                                                      total_zinc_load=curr_total_zinc,
                                                                      surface_type=surface_type)
    updated_values = {"total_suspended_solids": curr_tss,
                      "total_copper": curr_total_copper,
                      "total_zinc": curr_total_zinc,
                      "dissolved_copper": curr_dissolved_copper,
                      "dissolved_zinc": curr_dissolved_zinc}
    row.update(updated_values)
    return row


def run_medusa_model_for_surface_geometries(surfaces: gpd.GeoDataFrame,
                                            rainfall_event: MedusaRainfallEvent) -> gpd.GeoDataFrame:
    """
    Run the pollution model for a collection of surface geometries.
    For each of these it calculates the TSS, total metal load, and dissolved metal load. This runs for one rain event.

    Parameters
    ----------
    surfaces: gpd.GeoDataFrame
        A GeometryCollection containing surface geometries with surface type info to run MEDUSA model on.
    rainfall_event: MedusaRainfallEvent
        Rainfall event parameters for MEDUSA model.

    Returns
    -------
    gpd.GeoDataFrame
        The MEDUSA results for the given surfaces and rainfall_event.
    """
    # Add empty columns for each of the new medusa columns
    for medusa_column in ("total_suspended_solids", "total_copper", "total_zinc", "dissolved_copper", "dissolved_zinc"):
        surfaces[medusa_column] = pd.Series(dtype='float')
    # Wrap DataFrame.apply with progress_apply to add tqdm progress bar.
    tqdm.pandas()
    # Use vectorised operations to add all medusa columns to each row/surface
    surfaces = surfaces.progress_apply(lambda surface: run_medusa_model_for_single_surface(surface, rainfall_event),
                                       axis=1)
    return surfaces


def run_pollution_model_rain_event(engine: Engine,
                                   area_of_interest: gpd.GeoDataFrame,
                                   rainfall_event: MedusaRainfallEvent,
                                   ) -> int:
    """
    Run the pollution model for buildings (roofs), roads, and car parks and adds the results to the database.
    For each of these it calculates the TSS, total metal load, and dissolved metal load. This runs for one rain event.

    Parameters
    ----------
    engine: Engine
       The sqlalchemy database connection engine.
    area_of_interest: gpd.GeoDataFrame
        A GeoDataFrame polygon specifying the area of interest to retrieve buildings in.
    rainfall_event: MedusaRainfallEvent
        Rainfall event parameters for MEDUSA 2.0 model.

    Returns
    -------
    int
        The scenario ID of the pollution model run
    """
    log.info("Running MEDUSA2 pollution model for the area of interest.")
    calculation_pending_log_message = "Calculating pollutant load contributions for {features} in the area of interest."
    calculation_complete_log_message = "Pollutant load contributions calculated for {features} in the area of interest."

    all_buildings = get_building_information(engine, area_of_interest)
    all_roads = get_road_information(engine, area_of_interest)

    # Run through each building and calculate TSS, total metal loads, and dissolved metal loads
    log.info(calculation_pending_log_message.format(features="buildings"))
    all_buildings = run_medusa_model_for_surface_geometries(all_buildings, rainfall_event)
    log.info(calculation_complete_log_message.format(features="buildings"))

    # Run through all the roads/car parks, and calculate TSS, total metal loads, and dissolved metal loads
    log.info(calculation_pending_log_message.format(features="roads and car parks"))
    all_roads = run_medusa_model_for_surface_geometries(all_roads, rainfall_event)
    log.info(calculation_complete_log_message.format(features="roads and car parks"))

    # Drop the geometry columns now, since they can be joined to the spatial tables so we reduce data duplication
    all_buildings = all_buildings.drop("geometry", axis=1)
    all_roads = all_roads.drop('geometry', axis=1)

    log.info("Saving MEDUSA2 pollution model output to the database.")
    # Create the medusa2_model_output tables in the database if they don't already exist.
    create_table(engine, Medusa2ModelOutputBuildings)
    create_table(engine, Medusa2ModelOutputRoads)

    # Get the scenario ID for the current event
    scenario_id = get_next_scenario_id(engine)

    # Assign all rows in the local dataframe the same scenario ID. For some reason pylint gives a warning for this.
    all_buildings["scenario_id"] = scenario_id  # pylint: disable=unsupported-assignment-operation
    all_roads["scenario_id"] = scenario_id  # pylint: disable=unsupported-assignment-operation

    all_buildings.to_sql(Medusa2ModelOutputBuildings.__tablename__, engine, if_exists="append", index=True)
    all_roads.to_sql(Medusa2ModelOutputRoads.__tablename__, engine, if_exists="append", index=True)
    log.info("MEDUSA2 pollution model output saved to the database.")

    return scenario_id


def serve_pollution_model() -> None:
    """Serve the geospatial data for pollution models visualisation and API use.
    Joins the medusa2_model_output table to the corresponding geospatial feature tables.
    """
    # Create geoserver workspace for pollution data
    db_name = EnvVariable.POSTGRES_DB
    workspace_name = f"{db_name}-pollution"
    geoserver.create_workspace_if_not_exists(workspace_name)

    # Ensure workspace has access to database
    data_store_name = f"{db_name} PostGIS"
    geoserver.create_db_store_if_not_exists(db_name, workspace_name, data_store_name)

    # Serve each medusa2_model_output table joined to geometry from associated spatial table
    for medusa_table_class in [Medusa2ModelOutputRoads, Medusa2ModelOutputBuildings]:
        # Gather the names of the tables and columns
        medusa_table_name = medusa_table_class.__tablename__
        geometry_table_name = medusa_table_class.geometry_table
        spatial_id_column = medusa_table_class.spatial_feature_id.name

        # Construct query linking medusa_table_class to its geometry table
        pollution_sql_query = f"""
        SELECT medusa.*, geometry
        FROM {medusa_table_name} as medusa
             INNER JOIN {geometry_table_name} as spatial
                ON medusa.{spatial_id_column}=spatial.{spatial_id_column}
        """
        # Escape characters in SQL query so that it is valid Geoserver XML
        xml_escaped_sql = saxutils.escape(pollution_sql_query, entities={r"'": "&apos;", "\n": "&#xd;"})

        pollution_metadata_xml = rf"""
            <metadata>
              <entry key="JDBC_VIRTUAL_TABLE">
                <virtualTable>
                  <name>{medusa_table_name}</name>
                  <sql>
                    {xml_escaped_sql}
                  </sql>
                  <escapeSql>false</escapeSql>
                  <geometry>
                    <name>geometry</name>
                    <type>Geometry</type>
                    <srid>2193</srid>
                  </geometry>
                </virtualTable>
              </entry>
            </metadata>
            """
        # Add layer to geoserver based on SQL
        geoserver.create_datastore_layer(workspace_name,
                                         data_store_name,
                                         layer_name=medusa_table_name,
                                         metadata_elem=pollution_metadata_xml)


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
        result = conn.execute(f"SELECT MAX(scenario_id) FROM {Medusa2ModelOutputBuildings.__tablename__}").fetchone()[0]
        max_scenario_id = result if result is not None else 0
        return max_scenario_id + 1


def find_existing_pollution_scenario(engine: Engine,
                                     area_of_interest: gpd.GeoDataFrame,
                                     rainfall_event: MedusaRainfallEvent) -> Optional[int]:
    """
    Search the database for a pollution scenario with the same rainfall event parameters that covers the area.

    Parameters
    ----------
    engine: Engine
       The sqlalchemy database connection engine.
    area_of_interest: gpd.GeoDataFrame
        A GeoDataFrame polygon specifying the area of interest to retrieve buildings in.
    rainfall_event: MedusaRainfallEvent
        Rainfall event parameters for MEDUSA 2.0 model.

    Returns
    -------
    Optional[int]
        The scenario ID of the pollution model retrieved, or None if it does not exist
    """
    if not check_table_exists(engine, MedusaScenarios.__tablename__):
        # If there are no MedusaScenarios, then we will not be able to find one, return None
        return None

    # Retrieve geometry info in form ready for SQL query
    aoi_wkt = area_of_interest["geometry"][0].wkt
    crs = str(area_of_interest.crs.to_epsg())

    query = text("""
    SELECT scenario_id FROM medusa_scenarios WHERE
        antecedent_dry_days=:antecedent_dry_days
        AND average_rain_intensity=:average_rain_intensity
        AND event_duration=:event_duration
        AND rainfall_ph=:rainfall_ph
        AND ST_CONTAINS(geometry, ST_GeomFromText(:aoi_wkt, :crs))
    ORDER BY created_at
    LIMIT 1
    """).bindparams(aoi_wkt=aoi_wkt, crs=crs, **rainfall_event.as_dict())

    result = engine.execute(query).fetchone()
    if result is None:
        # No scenario found
        return None

    # Scenario found, pull from the result row
    scenario_id = result[0]
    log.info(f"Found existing MEDUSA scenario with matching parameters with id {scenario_id}.")
    return scenario_id


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
    area_of_interest = get_catchment_area(selected_polygon_gdf, to_crs=2193)

    # Wrap all parameters for MEDUSA rainfall event into a NamedTuple
    rainfall_event = MedusaRainfallEvent(antecedent_dry_days, average_rain_intensity, event_duration, rainfall_ph)

    # Search for a scenario that already exist, and return that one if it does.
    existing_scenario_id = find_existing_pollution_scenario(engine, area_of_interest, rainfall_event)
    if existing_scenario_id is not None:
        return existing_scenario_id

    # Run the pollution model
    scenario_id = run_pollution_model_rain_event(engine, area_of_interest, rainfall_event)

    # # Ensure pollution model data is being served by geoserver
    serve_pollution_model()

    # Create new table recording users' history
    create_table(engine, MedusaScenarios)
    # Record the input parameters used to create the scenario
    record_scenario_input_query = MedusaScenarios(
        scenario_id=scenario_id,
        antecedent_dry_days=antecedent_dry_days,
        average_rain_intensity=average_rain_intensity,
        event_duration=event_duration,
        rainfall_ph=rainfall_ph,
        geometry=area_of_interest['geometry'].to_wkt().iloc[0]
    )
    # Execute the query
    execute_query(engine, record_scenario_input_query)

    return scenario_id


def retrieve_input_parameters(scenario_id: int) -> Optional[Dict[str, Union[str, float]]]:
    """
    Retrieve input parameters for the current scenario id.

    Parameters
    ----------
    scenario_id: int
        The scenario ID of the pollution model run


    Returns
    -------
    Dict[str, Union[str, float]]
        A dictionary with information selected from Rainfall MEDUSA 2.0 database based on scenario ID
    """
    # Connect to the database
    engine = setup_environment.get_database()

    # Check table exists before querying
    if not check_table_exists(engine, 'medusa_scenarios'):
        return None

    else:
        # Set up query command to pull information from medusa_scenarios table
        query = text(
            "SELECT * FROM medusa_scenarios WHERE scenario_id = :scenario_id"
        ).bindparams(scenario_id=scenario_id)

        # Get information by using scenario_id from medusa_scenarios table in the dataset
        return engine.execute(query).fetchone()


if __name__ == "__main__":
    sample_polygon = gpd.GeoDataFrame.from_file("selected_polygon.geojson")
    main(
        selected_polygon_gdf=sample_polygon,
        log_level=LogLevel.DEBUG,
        antecedent_dry_days=1,
        average_rain_intensity=1,
        event_duration=1,
        rainfall_ph=6.5
    )
