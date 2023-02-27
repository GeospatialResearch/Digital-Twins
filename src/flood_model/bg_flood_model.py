# -*- coding: utf-8 -*-
"""
Created on Fri Jan 14 14:05:35 2022

@author: pkh35, sli229
"""
import logging
import json
import os
import pathlib
import subprocess
from datetime import datetime

import xarray as xr
from geoalchemy2 import Geometry
from sqlalchemy import Column, Integer, String
from sqlalchemy import DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from src import config
from src.digitaltwin import setup_environment
from src.dynamic_boundary_conditions.rainfall_enum import RainInputType
from src.lidar import dem_metadata_in_db

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


Base = declarative_base()


def bg_model_inputs(
        bg_path,
        dem_path,
        output_dir: pathlib.Path,
        catchment_boundary,
        resolution,
        end_time,
        output_timestep,
        rain_input_type: RainInputType,
        mask=15,
        gpu_device=0,
        small_nc=0
):
    """Set parameters to run the flood model.
    mask is used for visualising all the values larger than 15.
    If we are using the gpu then set to 0 (if no gpu type -1).
    smallnc = 0 means Level of refinement to apply to resolution based on the
    adaptive resolution trigger
    """
    now = datetime.now()
    dt_string = now.strftime("%Y_%m_%d_%H_%M_%S")
    with xr.open_dataset(dem_path) as file_nc:
        max_temp_xr = file_nc
    keys = max_temp_xr.data_vars.keys()
    elev_var = list(keys)[1]
    rainfall = "rain_forcing.txt" if rain_input_type == RainInputType.UNIFORM else "rain_forcing.nc?rain_intensity_mmhr"
    river = "RiverDis.txt"
    extents = "1575388.550,1575389.550,5197749.557,5197750.557"
    # BG Flood is not capable of creating output directories, so we must ensure this is done before running the model.
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)
    outfile = rf"{output_dir}/output_{dt_string}.nc"
    valid_bg_path = bg_model_path(bg_path)
    with open(rf"{valid_bg_path}/BG_param.txt", "w+") as param_file:
        param_file.write(f"topo = {dem_path}?{elev_var};\n"
                         f"gpudevice = {gpu_device};\n"
                         f"mask = {mask};\n"
                         f"dx = {resolution};\n"
                         f"smallnc = {small_nc};\n"
                         f"outputtimestep = {output_timestep};\n"
                         f"endtime = {end_time};\n"
                         f"rain = {rainfall};\n"
                         f"river = {river},{extents};\n"
                         f"outvars = h, hmax, zb, zs, u, v;\n"
                         f"outfile = {outfile};")
    model_output_to_db(outfile, catchment_boundary)
    river_discharge_info(bg_path)


def bg_model_path(file_path):
    """Check if the flood_model path exists."""
    model_file = pathlib.Path(file_path)
    if model_file.exists():
        return model_file
    raise FileNotFoundError(f"flood model {file_path} not found")


def model_output_to_db(outfile, catchment_boundary):
    """Store metadata of model output in database."""
    engine = setup_environment.get_database()
    BGDEM.__table__.create(bind=engine, checkfirst=True)
    filepath = outfile
    filename = os.path.basename(filepath)
    geometry = str(catchment_boundary["geometry"][0])
    flood_dem = BGDEM(filepath=filepath, Filename=filename, geometry=geometry)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(flood_dem)
    session.commit()


def river_discharge_info(bg_path):
    """Get the river discharge info. from design hydrographs."""
    with open(bg_path / "RiverDis.txt") as file:
        print(file.read())


class BGDEM(Base):
    """Class used to create model_output table in the database."""

    __tablename__ = "model_output"
    unique_id = Column(Integer, primary_key=True, autoincrement=True)
    filepath = Column(String)
    Filename = Column(String)
    access_date = Column(DateTime, default=datetime.now())
    geometry = Column(Geometry("POLYGON"))


def run_model(
        bg_path,
        output_dir: pathlib.Path,
        instructions,
        catchment_boundary,
        resolution,
        end_time,
        output_timestep,
        rain_input_type: RainInputType,
        engine
):
    """Call the functions."""
    dem_path = dem_metadata_in_db.get_dem_path(instructions, engine)
    bg_model_inputs(
        bg_path, dem_path, output_dir, catchment_boundary, resolution, end_time, output_timestep, rain_input_type
    )
    os.chdir(bg_path)
    subprocess.run([bg_path / "BG_flood.exe"], check=True)


def find_latest_model_output(output_dir: pathlib.Path):
    """
    Find the latest BG-Flood model output.

    Parameters
    ----------
    output_dir : pathlib.Path
        BG-Flood model output directory.
    """
    list_of_files = output_dir.glob("*.nc")
    try:
        latest_file = max(list_of_files, key=os.path.getctime)
    except ValueError:
        latest_file = None
        log.error(f"Missing BG-Flood Model output in: {output_dir}")
    return latest_file


def add_crs_to_latest_model_output(output_dir: pathlib.Path):
    """
    Add CRS to the latest BG-Flood Model Output.

    Parameters
    ----------
    output_dir : pathlib.Path
        BG-Flood model output directory.
    """
    latest_file = find_latest_model_output(output_dir)
    if latest_file is not None:
        with xr.open_dataset(latest_file, decode_coords="all") as latest_output:
            latest_output.load()
            if latest_output.rio.crs is None:
                latest_output.rio.write_crs("epsg:2193", inplace=True)
        latest_output.to_netcdf(latest_file)


def read_and_fill_instructions():
    """Reads instruction file and adds keys and uses selected_polygon.geojson as catchment_boundary"""
    linz_api_key = config.get_env_variable("LINZ_API_KEY")
    instruction_file = pathlib.Path("src/flood_model/instructions_geofabrics.json")
    with open(instruction_file, "r") as file_pointer:
        instructions = json.load(file_pointer)
    instructions["instructions"]["apis"]["vector"]["linz"]["key"] = linz_api_key
    instructions["instructions"]["data_paths"]["catchment_boundary"] = (
                pathlib.Path(os.getcwd()) / pathlib.Path("selected_polygon.geojson")).as_posix()
    instructions["instructions"]["data_paths"]["local_cache"] = instructions["instructions"]["data_paths"][
        "local_cache"].format(data_dir=config.get_env_variable("DATA_DIR"))
    return instructions


def main():
    engine = setup_environment.get_database()
    # BG-Flood Model directory
    flood_model_dir = config.get_env_variable("FLOOD_MODEL_DIR")
    bg_path = pathlib.Path(flood_model_dir)
    # BG-Flood Model output directory
    data_dir = config.get_env_variable("DATA_DIR")
    output_dir = pathlib.Path(data_dir) / "model_output"

    instructions = read_and_fill_instructions()
    catchment_boundary = dem_metadata_in_db.get_catchment_boundary()
    resolution = instructions["instructions"]["output"]["grid_params"]["resolution"]
    # Saving the outputs after each `outputtimestep` seconds
    output_timestep = 100.0
    # Saving the outputs till `endtime` number of seconds (or the output after `endtime` seconds
    # is the last one)
    end_time = 900.0
    run_model(
        bg_path=bg_path,
        output_dir=output_dir,
        instructions=instructions,
        catchment_boundary=catchment_boundary,
        resolution=resolution,
        end_time=end_time,
        output_timestep=output_timestep,
        rain_input_type=RainInputType.VARYING,
        engine=engine
    )
    add_crs_to_latest_model_output(output_dir)


if __name__ == "__main__":
    main()
