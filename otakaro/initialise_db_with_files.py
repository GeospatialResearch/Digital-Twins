"""Reads local disk geospatial data files and loads the data into database tables."""

import logging

import geopandas as gpd
from sqlalchemy.engine import Engine

from src.config import EnvVariable
from src.digitaltwin import setup_environment
from src.digitaltwin.tables import check_table_exists
from src.digitaltwin.utils import setup_logging
from src.digitaltwin.utils import LogLevel
from otakaro.pollution_model import pollution_tables as tables

setup_logging()
log = logging.getLogger(__name__)


def save_roof_surface_type_points_to_db(engine: Engine) -> None:
    """
    Read roof surface type points data then store them into database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    """
    # Check if the table already exist in the database
    if check_table_exists(engine, "roof_surface_points"):
        log.info("'roof_surface_points' data already exists in the database.")
    else:
        # Read roof surface points from outside
        # This data has the deeplearn_matclass with roof types we need
        log.info(f"Reading roof surface points from {EnvVariable.ROOF_SURFACE_DATASET_PATH}.")
        roof_surface_points = gpd.read_file(EnvVariable.ROOF_SURFACE_DATASET_PATH,
                                            layer="CCC_Lynker_RoofMaterial_Update_2023")
        # Remove rows of building_Id and deeplearn_subclass that are NANs
        roof_surface_points = roof_surface_points.dropna(subset=['building_Id', 'deeplearn_subclass'])
        # Store the building_point_data to the database table
        log.info("Adding 'roof_surface_points' to the database.")
        roof_surface_points.to_postgis("roof_surface_points", engine, index=False, if_exists="replace")
        log.info("Successfully added 'roof_surface_points' to the database.")


def save_roof_surface_polygons_to_db(engine: Engine) -> None:
    """
    Read roof surface polygons data then store them into database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    """
    # Check if the table already exist in the database
    if check_table_exists(engine, "roof_surface_polygons"):
        log.info("'roof_surface_polygons' data already exists in the database.")
    else:
        # Read roof surface polygons from outside
        log.info(f"Reading roof surface polygons file {EnvVariable.ROOF_SURFACE_DATASET_PATH}.")
        roof_surface_polygons = gpd.read_file(EnvVariable.ROOF_SURFACE_DATASET_PATH, layer="BuildingPolygons")
        # Store the building_point_data to the database table
        log.info("Adding 'roof_surface_polygons' to the database.")
        roof_surface_polygons.to_postgis("roof_surface_polygons", engine, index=False, if_exists="replace")
        log.info("Successfully added 'roof_surface_polygons' to the database.")


# noinspection PyIncorrectDocstring
def main(
    _selected_polygon_gdf: gpd.GeoDataFrame = None,
    log_level: LogLevel = LogLevel.DEBUG
) -> None:
    """
    Read file-based geospatial data and load into database tables.

    Parameters
    ----------
    log_level : LogLevel = LogLevel.DEBUG
        The log level to set for the root logger. Defaults to LogLevel.DEBUG.
        The available logging levels and their corresponding numeric values are:
        - LogLevel.CRITICAL (50)
        - LogLevel.ERROR (40)
        - LogLevel.WARNING (30)
        - LogLevel.INFO (20)
        - LogLevel.DEBUG (10)
        - LogLevel.NOTSET (0)
    """
    # Set up logging with the specified log level
    setup_logging(log_level)
    # Connect to the database
    engine = setup_environment.get_database()
    # Define custom database functions to aid querying.
    tables.define_custom_db_functions(engine)
    # Read roof surface type points data then store them into database.
    save_roof_surface_type_points_to_db(engine)
    # Read roof surface polygons data then store them into database.
    save_roof_surface_polygons_to_db(engine)
