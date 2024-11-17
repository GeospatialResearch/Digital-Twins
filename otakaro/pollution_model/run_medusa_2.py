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
from otakaro.pollution_model.pollution_tables import Medusa2ModelOutputBuildings, Medusa2ModelOutputRoads
from otakaro.pollution_model.pollution_tables import MedusaScenarios

log = logging.getLogger(__name__)


# Enum strings are assigned as they are described in the original paper
class SurfaceType(StrEnum):
    """
    StrEnum to represent the surface types that a feature could have.

    Attributes
    ----------
    COLORSTEEL : str
        Colorsteel surface
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

    COLORSTEEL = "Colorsteel"
    GALVANISED = "Galvanised"
    METAL_OTHER = "MetalOther"
    METAL_TILE = "MetalTile"
    NON_METAL = "NonMetal"
    ZINCALUME = "Zincalume"
    ASPHALT_ROAD = "AsphaltRoad"
    CAR_PARK = "CarPark"  # CarParks are classified the same as roads


ROOF_SURFACE_TYPES = {SurfaceType.COLORSTEEL, SurfaceType.GALVANISED, SurfaceType.METAL_OTHER, SurfaceType.METAL_TILE,
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
        Amount of copper load contributed by a step in the pollutant model (milligrams).
    zn_load: float
        Amount of zinc load contributed by a step in the pollutant model (milligrams).
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
       Returns the TSS value from the given parameters (milligrams)

    Raises
    ----------
    ValueError
        If the surface type is not a roof or road (concrete, copper, galvanised roof, asphalt road, or car park).
    """
    # Define error message (if needed)
    invalid_surface_error = (f"Given surface is not valid for computing TSS."
                             f" Needed a roof or road, but got {SurfaceType(surface_type).name}.")

    match surface_type:
        case SurfaceType.COLORSTEEL:
            # Galvanised Painted
            a1, a2, k = 0.4, 0.5, 0.00933
        case SurfaceType.GALVANISED:
            # Galvanised
            a1, a2, k = 0.4, 0.5, 0.00933
        case SurfaceType.METAL_OTHER:
            # Copper Old
            # Using coefficients of Galvanised rather than Copper as suggested by Francis
            # Email named 'Aligning CCC Surface Type data with Okeover
            a1, a2, k = 0.4, 0.5, 0.00933
        case SurfaceType.METAL_TILE:
            # Decramastic
            a1, a2, k = 0.4, 0.5, 0.00933
        case SurfaceType.NON_METAL:
            # Concrete, Concrete Painted, and Glass Roof
            a1, a2, k = 0.6, 0.25, 0.00933
        case SurfaceType.ZINCALUME:
            # Zincalume
            a1, a2, k = 0.4, 0.5, 0.00933
        case SurfaceType.ASPHALT_ROAD | SurfaceType.CAR_PARK:
            a1, a2, k = 190, 0.16, 0.0008
        case _:
            raise ValueError(invalid_surface_error)

    # Call out necessary variables
    antecedent_dry_days, average_rain_intensity, event_duration, _ph = rainfall_event

    # Calculate tss for road and roof
    if surface_type == 'AsphaltRoad':
        # Road
        first_term = a1 * (antecedent_dry_days ** a2) * surface_area * 0.25
    else:
        # Roof
        first_term = a1 * (antecedent_dry_days ** a2) * surface_area * 0.75

    # Second term appears in both road and roof calculation
    second_term = 1 - math.exp(-k * average_rain_intensity * event_duration)

    return first_term * second_term * 1000


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
       Returns the total copper and zinc loads from the given parameters (milligrams).

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
       Returns the total copper and zinc loads from the given parameters (milligrams).

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
        case SurfaceType.COLORSTEEL:
            # None was added to avoid the 0 position when indexing
            b = [None, 2, -2.802, 0.5, 0.217, 3.57, -0.09, 7, -3.732]
            c = [None, 910, 4, 0.2, 0.09, 1.5, -2, -0.23, 1.99]
            # Duration of the event measured by hours - Roof
            # observed from the intra-event concentration sampling
            z = 0.75
        case SurfaceType.GALVANISED:
            # None was added to avoid the 0 position when indexing
            b = [None, 2, -2.802, 0.5, 0.217, 3.57, -0.09, 7, -3.732]
            c = [None, 910, 4, 0.2, 0.09, 1.5, -2, -0.23, 1.99]
            # Duration of the event measured by hours - Roof
            # observed from the intra-event concentration sampling
            z = 0.75
        case SurfaceType.METAL_OTHER:
            # None was added to avoid the 0 position when indexing
            # Using coefficients of Galvanised rather than Copper as suggested by Frances
            # Email named 'Aligning CCC Surface Type data with Okeover
            b = [None, 2, -2.802, 0.5, 0.217, 3.57, -0.09, 7, -3.732]
            c = [None, 910, 4, 0.2, 0.09, 1.5, -2, -0.23, 1.99]
            # Duration of the event measured by hours - Roof
            # observed from the intra-event concentration sampling
            z = 0.75
        case SurfaceType.METAL_TILE:
            # None was added to avoid the 0 position when indexing
            b = [None, 2, -2.802, 0.5, 0.217, 3.57, -0.09, 7, -3.732]
            c = [None, 910, 4, 0.2, 0.09, 1.5, -2, -0.23, 1.99]
            # Duration of the event measured by hours - Roof
            # observed from the intra-event concentration sampling
            z = 0.75
        case SurfaceType.NON_METAL:
            # None was added to avoid the 0 position when indexing
            b = [None, 2, -2.802, 0.5, 0.217, 3.57, -0.09, 7, -3.732]
            c = [None, 50, 2600, 0.1, 0.01, 1, -3.1, -0.007, 0.056]
            # Duration of the event measured by hours - Roof
            # observed from the intra-event concentration sampling
            z = 0.75
        case SurfaceType.ZINCALUME:
            # None was added to avoid the 0 position when indexing
            b = [None, 2, -2.802, 0.5, 0.217, 3.57, -0.09, 7, -3.732]
            c = [None, 910, 4, 0.2, 0.09, 1.5, -2, -0.23, 1.99]
            # Duration of the event measured by hours - Roof
            # observed from the intra-event concentration sampling
            z = 0.75
        case _:
            raise ValueError(invalid_surface_error)

    # Get necessary parameters
    antecedent_dry_days, average_rain_intensity, event_duration, rainfall_ph = rainfall_event

    # Define the initial and second stages of Roof Copper Load.
    # Initial stage
    cu_o = b[1] * (rainfall_ph ** b[2])
    cu_o *= b[3] * (antecedent_dry_days ** b[4])
    cu_o *= b[5] * (average_rain_intensity ** b[6])
    # Second stage
    cu_est = b[7] * (rainfall_ph ** b[8])
    # Calculate k
    k_cu = (-math.log(cu_est / cu_o)) / (average_rain_intensity * z)

    # Define the initial and second stages of Roof Zinc Load.
    # Initial stage
    zn_o = (c[1] * rainfall_ph) + c[2]
    zn_o *= c[3] * (antecedent_dry_days ** c[4])
    zn_o *= c[5] * (average_rain_intensity ** c[6])
    # Second stage
    zn_est = (c[7] * rainfall_ph) + c[8]
    # Calculate k
    k_zn = (-math.log(zn_est / zn_o)) / (average_rain_intensity * z)

    # Common factors for each of initial Copper and Zinc Loads
    cu_factor = cu_o * surface_area * (1 / (1000 * k_cu))
    zn_factor = zn_o * surface_area * (1 / (1000 * k_zn))

    # Calculate total metal loads, where the method depends on if Z is less than event_duration
    if event_duration < z:
        # Calculate total loads
        total_copper_load = cu_factor * (1 - math.exp(-k_cu * average_rain_intensity * event_duration))
        total_zinc_load = zn_factor * (1 - math.exp(-k_zn * average_rain_intensity * event_duration))

    else:
        # Calculate factors that appear in both Copper and Zinc formulas
        both_factor_est = surface_area * average_rain_intensity * (event_duration - z)

        # Calculate initial total loads
        initial_total_copper_load = cu_factor * (1 - math.exp(-k_cu * average_rain_intensity * z))
        initial_total_zinc_load = zn_factor * (1 - math.exp(-k_zn * average_rain_intensity * z))

        # Calculate total loads for Copper and Zinc roofs
        total_copper_load = initial_total_copper_load + (cu_est * both_factor_est)
        total_zinc_load = initial_total_zinc_load + (zn_est * both_factor_est)

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
       Returns the total copper and zinc loads for this surface (milligrams)
       [Total Copper, Total Zinc]
    """
    # Define constants
    g = 0.441
    h = 1.96
    total_cu_load = tss_surface * g
    total_zn_load = tss_surface * h
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
        Returns the dissolved copper and zinc load for this surface (milligrams)
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
        case SurfaceType.COLORSTEEL:
            # Galvanised Painted
            l1 = 0.5
            m1 = 0.43
        case SurfaceType.GALVANISED:
            # Galvanised
            l1 = 0.5
            m1 = 0.43
        case SurfaceType.METAL_OTHER:
            # Copper Old
            l1 = 0.77
            m1 = 0.717
        case SurfaceType.METAL_TILE:
            # Decramastic
            l1 = 0.5
            m1 = 0.43
        case SurfaceType.NON_METAL:
            # Concrete, Concrete Painted, and Glass Roof
            l1 = 0.77
            m1 = 0.67
        case SurfaceType.ZINCALUME:
            l1 = 0.5
            m1 = 0.43
        case SurfaceType.ASPHALT_ROAD | SurfaceType.CAR_PARK:
            l1 = 0.28
            m1 = 0.43
        case _:
            raise ValueError(invalid_surface_error)
    return MetalLoads(l1 * total_copper_load, m1 * total_zinc_load)


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
        ORDER BY polygons."building_Id"
    """).bindparams(aoi_wkt=str(aoi_wkt), crs=str(crs))

    # Execute the SQL query
    buildings = gpd.GeoDataFrame.from_postgis(query, engine, index_col="building_Id", geom_col="geometry")

    # Some buildings have multiple points, we can only define a building as one surface type without duplicating area.
    # So we drop duplicates by building_Id (index).
    buildings = buildings[~buildings.index.duplicated(keep='first')]

    # The CCC dataset has ColourSteel as a surface type, but the correct spelling of the brand is Colorsteel
    # Replace all "ColourSteel" with "Colorsteel"
    buildings["surface_type"][buildings["surface_type"] == "ColourSteel"] = SurfaceType.COLORSTEEL

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
        # Roughly approximate the surface area of a road by assuming it's width is 5m
        surface_area = row.geometry.length * 5
    else:
        surface_area = row.geometry.area

    # Calculate total suspended solids contributed by surface
    curr_tss = compute_tss_roof_road(surface_area, rainfall_event, surface_type)

    # Calculate total copper and total zinc contributed by surface
    curr_total_copper, curr_total_zinc = total_metal_load_surface(surface_area,
                                                                  rainfall_event,
                                                                  surface_type,
                                                                  curr_tss)

    # Calculate dissolved copper and dissolved zinc contributed by surface
    curr_dissolved_copper, curr_dissolved_zinc = dissolved_metal_load(total_copper_load=curr_total_copper,
                                                                      total_zinc_load=curr_total_zinc,
                                                                      surface_type=surface_type)
    # Update the current row with the values found for each MEDUSA column.
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
    medusa_columns = ["total_suspended_solids", "total_copper", "total_zinc", "dissolved_copper", "dissolved_zinc"]
    for medusa_column in medusa_columns:
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
        significant_figures = 5
        pollution_sql_query = f"""
        SELECT
            sig_fig(total_suspended_solids, {significant_figures})
                AS "Total Suspended Solids (mg)",
            sig_fig(dissolved_zinc, {significant_figures})
                AS "Dissolved Zinc (mg)",
            sig_fig(total_zinc, {significant_figures})
                AS "Total Zinc (mg)",
            sig_fig(dissolved_copper, {significant_figures})
                AS "Dissolved Copper (mg)",
            sig_fig(total_copper, {significant_figures})
                AS "Total Copper (mg)",
            surface_type,
            scenario_id,
            spatial."{spatial_id_column}",
            ST_AREA(geometry) as "Area (m²)",
            geometry
        FROM {medusa_table_name} as medusa
             INNER JOIN {geometry_table_name} as spatial
                ON medusa."{spatial_id_column}"=spatial."{spatial_id_column}"
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
         rainfall_ph: float = 6.5) -> int:
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
       The scenario id of the new medusa scenario produced
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
        serve_pollution_model()
        return existing_scenario_id

    # Run the pollution model
    scenario_id = run_pollution_model_rain_event(engine, area_of_interest, rainfall_event)

    # Ensure pollution model data is being served by geoserver
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
        geometry=area_of_interest["geometry"][0].wkt
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
        antecedent_dry_days=1.45833333333333,
        average_rain_intensity=0.5,
        event_duration=2,
        rainfall_ph=6.5
    )
