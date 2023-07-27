# -*- coding: utf-8 -*-
"""
Created on Wed Nov 10 13:22:27 2021.
@author: pkh35, sli229
"""

import logging
import pathlib
import json
from typing import Tuple, Dict, Any, Union

import geopandas as gpd
import xarray as xr
import rioxarray as rxr
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base

from src import config
from src.digitaltwin import setup_environment
from src.digitaltwin.tables import HydroDEM, create_table, execute_query
import geofabrics.processor

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)

Base = declarative_base()


def get_hydro_dem_metadata(
        instructions: Dict[str, Any],
        catchment_boundary: gpd.GeoDataFrame) -> Tuple[str, str, str]:
    """Get the hydrological DEM metadat~a."""
    data_paths: Dict[str, Any] = instructions["instructions"]["data_paths"]
    result_dem_path = pathlib.Path(data_paths["local_cache"]) / data_paths["subfolder"] / data_paths["result_dem"]
    hydro_dem_name = result_dem_path.name
    hydro_dem_path = result_dem_path.as_posix()
    catchment_geom = catchment_boundary["geometry"].to_wkt().iloc[0]
    return hydro_dem_name, hydro_dem_path, catchment_geom


def store_hydro_dem_metadata_to_db(
        engine: Engine,
        instructions: Dict[str, Any],
        catchment_boundary: gpd.GeoDataFrame) -> None:
    """Store metadata of the hydrologically conditioned DEM in the database."""
    create_table(engine, HydroDEM)
    hydro_dem_name, hydro_dem_path, geometry = get_hydro_dem_metadata(instructions, catchment_boundary)
    query = HydroDEM(file_name=hydro_dem_name, file_path=hydro_dem_path, geometry=geometry)
    execute_query(engine, query)
    log.info("Hydro DEM metadata for the catchment area successfully stored in the database.")


def check_hydro_dem_exist(engine: Engine, catchment_boundary: gpd.GeoDataFrame) -> bool:
    """Check if hydro DEM already exists in the database for the catchment area."""
    create_table(engine, HydroDEM)
    catchment_geom = catchment_boundary["geometry"].iloc[0]
    query = f"""
    SELECT EXISTS (
    SELECT 1
    FROM hydrological_dem
    WHERE ST_Equals(geometry, ST_GeomFromText('{catchment_geom}', 2193))
    );"""
    return engine.execute(query).scalar()


def read_and_fill_instructions(catchment_file_path: pathlib.Path) -> Dict[str, Any]:
    """Reads instruction file and adds keys and uses selected_polygon.geojson as catchment_boundary"""
    linz_api_key = config.get_env_variable("LINZ_API_KEY")
    instruction_file = pathlib.Path("src/flood_model/instructions_geofabrics.json")
    with open(instruction_file, "r") as file_pointer:
        instructions = json.load(file_pointer)
        instructions["instructions"]["apis"]["vector"]["linz"]["key"] = linz_api_key
        instructions["instructions"]["data_paths"]["catchment_boundary"] = catchment_file_path.as_posix()
        instructions["instructions"]["data_paths"]["local_cache"] = instructions["instructions"]["data_paths"][
            "local_cache"].format(data_dir=config.get_env_variable("DATA_DIR"))
    return instructions


def create_temp_catchment_boundary_file(selected_polygon_gdf: gpd.GeoDataFrame) -> pathlib.Path:
    """Temporary catchment file to be ingested by GeoFabrics"""
    temp_dir = pathlib.Path("tmp/geofabrics_polygons")
    # Create temporary storage folder if it does not already exist
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_file_path = temp_dir / "selected_polygon.geojson"
    selected_polygon_gdf.to_file(temp_file_path.as_posix(), driver='GeoJSON')
    return pathlib.Path.cwd() / temp_file_path


def remove_temp_catchment_boundary_file(file_path: pathlib.Path) -> None:
    """Removes the temporary file from the file system once it is used"""
    file_path.unlink()


def run_geofabrics_hydro_dem(instructions: Dict[str, Any]) -> None:
    """Use geofabrics to generate the hydrologically conditioned DEM."""
    runner = geofabrics.processor.RawLidarDemGenerator(instructions["instructions"])
    runner.run()
    runner = geofabrics.processor.HydrologicDemGenerator(instructions["instructions"])
    runner.run()
    log.info("Hydro DEM for the catchment area successfully generated.")


def generate_hydro_dem(
        engine: Engine,
        instructions: Dict[str, Any],
        catchment_boundary: gpd.GeoDataFrame) -> None:
    """Generate the hydrologically conditioned DEM for the catchment area."""
    if not check_hydro_dem_exist(engine, catchment_boundary):
        run_geofabrics_hydro_dem(instructions)
        store_hydro_dem_metadata_to_db(engine, instructions, catchment_boundary)
    else:
        log.info("Hydro DEM for the catchment area already exists in the database.")


def get_catchment_hydro_dem_filepath(
        engine: Engine,
        catchment_area: gpd.GeoDataFrame) -> pathlib.Path:
    """
    Retrieves the file path of the Hydrologically conditioned DEM (Hydro DEM) for the specified catchment area.

    Parameters
    ----------
    engine : Engine
        Engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.

    Returns
    -------
    pathlib.Path
        The file path of the Hydrologically conditioned DEM (Hydro DEM) for the specified catchment area.
    """
    # Extract the geometry of the catchment area
    catchment_polygon = catchment_area["geometry"].iloc[0]
    # Construct the query to retrieve the Hydro DEM file path
    query = f"""
    SELECT file_path
    FROM hydrological_dem
    WHERE ST_Equals(geometry, ST_GeomFromText('{catchment_polygon}', 2193));
    """
    # Execute the query and retrieve the Hydro DEM file path
    hydro_dem_filepath = engine.execute(query).scalar()
    # Convert the file path to a pathlib.Path object
    return pathlib.Path(hydro_dem_filepath)


def get_hydro_dem_data_and_resolution(
        engine: Engine,
        catchment_area: gpd.GeoDataFrame) -> Tuple[xr.Dataset, Union[int, float]]:
    """
    Retrieves the Hydrologically Conditioned DEM (Hydro DEM) data and resolution for the specified catchment area.

    Parameters
    ----------
    engine : Engine
        Engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.

    Returns
    -------
    Tuple[xr.Dataset, Union[int, float]]
        A tuple containing the Hydro DEM data as a xarray Dataset and the resolution as an integer or float.

    Raises
    ------
    ValueError
        If there is an inconsistency between the resolution in the metadata and the actual resolution of the Hydro DEM.
    """
    # Retrieve the file path of the Hydro DEM for the specified catchment area
    hydro_dem_filepath = get_catchment_hydro_dem_filepath(engine, catchment_area)
    # Open the Hydro DEM using rioxarray
    hydro_dem = rxr.open_rasterio(hydro_dem_filepath)
    # Select the first band of the Hydro DEM
    hydro_dem = hydro_dem.sel(band=1)
    # Get the unique resolution from the Hydro DEM
    unique_resolution = list(set(abs(res) for res in hydro_dem.rio.resolution()))
    # Check if there is only one unique resolution
    res_no = unique_resolution[0] if len(unique_resolution) == 1 else None
    # Get the resolution from the Hydro DEM description
    res_description = int(hydro_dem.description.split()[-1])
    # Check if the resolution from the metadata matches the actual resolution
    if res_no != res_description:
        raise ValueError("Inconsistent resolution between metadata and actual resolution of the Hydro DEM.")
    else:
        return hydro_dem, res_no


def main(selected_polygon_gdf: gpd.GeoDataFrame) -> None:
    engine = setup_environment.get_database()
    catchment_file_path = create_temp_catchment_boundary_file(selected_polygon_gdf)
    instructions = read_and_fill_instructions(catchment_file_path)
    generate_hydro_dem(engine, instructions, selected_polygon_gdf)
    remove_temp_catchment_boundary_file(catchment_file_path)


if __name__ == "__main__":
    sample_polygon = gpd.GeoDataFrame.from_file("selected_polygon.geojson")
    main(sample_polygon)
