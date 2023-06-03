# -*- coding: utf-8 -*-
"""
Created on Fri Jan 14 14:05:35 2022

@author: pkh35, sli229
"""

import logging
import pathlib
import os
import json
import subprocess
from datetime import datetime
from typing import Tuple, Dict, Any, Union

import geopandas as gpd
import xarray as xr
from geoalchemy2 import Geometry
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

from src import config
from src.digitaltwin import setup_environment
from src.lidar import dem_metadata_in_db
from src.dynamic_boundary_conditions.rainfall_enum import RainInputType
from src.flood_model.serve_model import add_model_output_to_geoserver

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)

Base = declarative_base()


def check_bg_flood_dir_exists(bg_flood_dir: pathlib.Path) -> pathlib.Path:
    """Check if the flood model directory exists."""
    if bg_flood_dir.exists() and bg_flood_dir.is_dir():
        return bg_flood_dir
    raise FileNotFoundError(f"BG-Flood Model not found at: '{bg_flood_dir}'.")


def latest_model_output_filepath_from_db(engine: Engine) -> pathlib.Path:
    """Retrieve the latest model output file path, by querying the database"""
    row = engine.execute("SELECT * FROM bg_flood_model_output ORDER BY created_at DESC LIMIT 1 ").fetchone()
    return pathlib.Path(row["file_path"])


def add_crs_to_latest_model_output(engine: Engine) -> None:
    """
    Add CRS to the latest BG-Flood Model Output.
    """
    latest_file = latest_model_output_filepath_from_db(engine)
    with xr.open_dataset(latest_file, decode_coords="all") as latest_output:
        latest_output.load()
        if latest_output.rio.crs is None:
            latest_output.rio.write_crs("epsg:2193", inplace=True)
    latest_output.to_netcdf(latest_file)


def process_tide_input_files(tide_input_file_path: pathlib.Path) -> Tuple[str, str]:
    tide_position = tide_input_file_path.stem.split('_')[0]
    tide_file = tide_input_file_path.name
    return tide_position, tide_file


def process_river_input_files(river_input_file_path: pathlib.Path) -> str:
    file_name_parts = river_input_file_path.stem.split('_')
    file_name = file_name_parts[0] + river_input_file_path.suffix
    extents = ','.join(file_name_parts[1:])
    river = f"{file_name},{extents}"
    new_file_path = river_input_file_path.with_name(file_name)
    river_input_file_path.rename(new_file_path)
    return river


class BGFloodModelOutput(Base):
    """Class used to create the 'bg_flood_model_output' table in the database."""
    __tablename__ = "bg_flood_model_output"
    unique_id = Column(Integer, primary_key=True, autoincrement=True)
    file_name = Column(String)
    file_path = Column(String)
    created_at = Column(DateTime(timezone=True), default=datetime.now(), comment="output created datetime")
    geometry = Column(Geometry("GEOMETRY", srid=2193), comment="catchment area coverage")


def create_model_output_table(engine: Engine) -> None:
    """Create bg_flood_model_output table if it doesn't exist."""
    BGFloodModelOutput.__table__.create(bind=engine, checkfirst=True)


def get_model_output_metadata(
        model_output_path: pathlib.Path,
        catchment_boundary: gpd.GeoDataFrame) -> Tuple[str, str, str]:
    """Get bg flood model output metadata"""
    output_name = model_output_path.name
    output_path = model_output_path.as_posix()
    catchment_geom = catchment_boundary["geometry"].to_wkt().iloc[0]
    return output_name, output_path, catchment_geom


def store_model_output_metadata_to_db(
        engine: Engine,
        model_output_path: pathlib.Path,
        catchment_boundary: gpd.GeoDataFrame) -> None:
    """Store metadata of the bg flood model output in the database."""
    create_model_output_table(engine)
    output_name, output_path, geometry = get_model_output_metadata(model_output_path, catchment_boundary)
    with Session(engine) as session:
        model_output = BGFloodModelOutput(file_name=output_name, file_path=output_path, geometry=geometry)
        session.add(model_output)
        session.commit()
        log.info("BG-Flood model output metadata stored successfully in the database.")


def get_bg_flood_model_inputs(
        bg_flood_dir: pathlib.Path,
        model_output_path: pathlib.Path,
        dem_path: pathlib.Path,
        resolution: Union[int, float],
        output_timestep: Union[int, float],
        end_time: Union[int, float],
        mask: Union[int, float] = 9999,
        gpu_device: int = 0,
        small_nc: int = 0,
        rain_input_type: RainInputType = RainInputType.UNIFORM) -> None:
    """
    Set parameters to run the flood model.
    mask is used for visualising all the values larger than 9999 by default.
    If we are using the gpu then set to 0 (if no gpu type -1).
    small_nc = 0 means Level of refinement to apply to resolution based on the adaptive resolution trigger
    """
    with xr.open_dataset(dem_path) as dem_file:
        elev_var = list(dem_file.data_vars)[1]
    bg_param_path = bg_flood_dir / "BG_param.txt"
    outfile = model_output_path.as_posix()
    rainfall = "rain_forcing.txt" if rain_input_type == RainInputType.UNIFORM else "rain_forcing.nc?rain_intensity_mmhr"
    with open(bg_param_path, "w+") as param_file:
        param_file.write(f"topo = {dem_path.as_posix()}?{elev_var};\n"
                         f"dx = {resolution};\n"
                         f"outputtimestep = {output_timestep};\n"
                         f"endtime = {end_time};\n"
                         f"mask = {mask};\n"
                         f"gpudevice = {gpu_device};\n"
                         f"smallnc = {small_nc};\n"
                         f"outfile = {outfile};\n"
                         f"outvars = h, hmax, zb, zs, u, v;\n"
                         f"rain = {rainfall};\n")
        for tide_input_file_path in bg_flood_dir.glob('*_bnd.txt'):
            tide_position, tide_file = process_tide_input_files(tide_input_file_path)
            param_file.write(f"{tide_position} = {tide_file},2;\n")
        for river_input_file_path in bg_flood_dir.glob('river[0-9]*_*.txt'):
            river = process_river_input_files(river_input_file_path)
            param_file.write(f"river = {river};\n")


def run_bg_flood_model(
        engine,
        bg_flood_dir: pathlib.Path,
        model_output_dir: pathlib.Path,
        instructions: Dict[str, Any],
        catchment_boundary: gpd.GeoDataFrame,
        output_timestep: Union[int, float],
        end_time: Union[int, float],
        mask: Union[int, float] = 9999,
        gpu_device: int = 0,
        small_nc: int = 0,
        rain_input_type: RainInputType = RainInputType.UNIFORM) -> None:
    dem_path = dem_metadata_in_db.get_catchment_hydro_dem_filepath(engine, catchment_boundary)
    # Check BG-Flood Model directory exists
    bg_flood_dir = check_bg_flood_dir_exists(bg_flood_dir)
    # Create model output folder if it does not already exist
    model_output_dir.mkdir(parents=True, exist_ok=True)
    dt_string = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    model_output_path = (model_output_dir / f"output_{dt_string}.nc")
    resolution = instructions["instructions"]["output"]["grid_params"]["resolution"]

    get_bg_flood_model_inputs(
        bg_flood_dir=bg_flood_dir,
        model_output_path=model_output_path,
        dem_path=dem_path,
        resolution=resolution,
        output_timestep=output_timestep,
        end_time=end_time,
        mask=mask,
        gpu_device=gpu_device,
        small_nc=small_nc,
        rain_input_type=rain_input_type)

    cwd = pathlib.Path.cwd()
    os.chdir(bg_flood_dir)
    subprocess.run([bg_flood_dir / "BG_flood.exe"], check=True)
    os.chdir(cwd)

    store_model_output_metadata_to_db(engine, model_output_path, catchment_boundary)
    add_crs_to_latest_model_output(engine)
    add_model_output_to_geoserver(model_output_path)


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


def main(selected_polygon_gdf: gpd.GeoDataFrame) -> None:
    engine = setup_environment.get_database()
    bg_flood_dir = config.get_env_variable("FLOOD_MODEL_DIR", cast_to=pathlib.Path)
    model_output_dir = config.get_env_variable("DATA_DIR_MODEL_OUTPUT", cast_to=pathlib.Path)
    catchment_file_path = create_temp_catchment_boundary_file(selected_polygon_gdf)
    instructions = read_and_fill_instructions(catchment_file_path)

    run_bg_flood_model(
        engine=engine,
        bg_flood_dir=bg_flood_dir,
        model_output_dir=model_output_dir,
        instructions=instructions,
        catchment_boundary=selected_polygon_gdf,
        output_timestep=100,  # Saving the outputs after each `outputtimestep` seconds
        end_time=900,  # Saving the outputs till `endtime` number of seconds
        rain_input_type=RainInputType.UNIFORM)

    remove_temp_catchment_boundary_file(catchment_file_path)


if __name__ == "__main__":
    sample_polygon = gpd.GeoDataFrame.from_file("selected_polygon.geojson")
    main(sample_polygon)
