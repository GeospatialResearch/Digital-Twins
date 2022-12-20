# -*- coding: utf-8 -*-
"""
Created on Fri Jan 14 14:05:35 2022

@author: pkh35, sli229
"""

import pathlib
import sys
import json
import xarray as xr
from datetime import datetime
import subprocess
from dotenv import load_dotenv
from typing import Literal
import os
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String
from geoalchemy2 import Geometry
from sqlalchemy.orm import sessionmaker
from sqlalchemy import DateTime
from src.digitaltwin import setup_environment
from src.lidar import dem_metadata_in_db

Base = declarative_base()


def bg_model_inputs(
        bg_path,
        dem_path,
        catchment_boundary,
        resolution,
        end_time,
        output_timestep,
        rain_input_type: Literal["uniform", "varying"],
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
    river = "RiverDis.txt"
    rainfall = "rain_forcing.txt" if rain_input_type == "uniform" else "rain_forcing.nc?rain_intensity_mmhr"
    extents = "1575388.550,1575389.550,5197749.557,5197750.557"
    outfile = rf"U:/Research/FloodRiskResearch/DigitalTwin/LiDAR/model_output/output_{dt_string}.nc"
    valid_bg_path = bg_model_path(bg_path)
    try:
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
    except Exception as error:
        print(error, type(error))
        sys.exit()
    model_output_to_db(outfile, catchment_boundary)
    river_discharge_info(bg_path)


def bg_model_path(file):
    """Check if the flood_model path exists."""
    file = pathlib.Path(file)
    if file.exists():
        return file
    else:
        print("directory doesn't exist")
        sys.exit()


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
        instructions,
        catchment_boundary,
        resolution,
        end_time,
        output_timestep,
        rain_input_type: Literal["uniform", "varying"],
        engine
):
    """Call the functions."""
    dem_path = dem_metadata_in_db.get_dem_path(instructions, engine)
    bg_model_inputs(
        bg_path, dem_path, catchment_boundary, resolution, end_time, output_timestep, rain_input_type
    )
    os.chdir(bg_path)
    subprocess.call([bg_path / "BG_Flood_Cleanup.exe"])


def get_api_key(key_name: str):
    """Get the required api key from dotenv environment variable file"""
    env_path = pathlib.Path().cwd() / "src" / ".env"
    load_dotenv(env_path)
    api_key = os.getenv(key_name)
    return api_key


def main():
    engine = setup_environment.get_database()
    bg_path = pathlib.Path(r"U:/Research/FloodRiskResearch/DigitalTwin/BG-Flood/BG-Flood_Win10_v0.6-a")
    linz_api_key = get_api_key("LINZ_API_KEY")
    instruction_file = pathlib.Path("src/lidar/instructions_bgflood.json")
    with open(instruction_file, "r") as file_pointer:
        instructions = json.load(file_pointer)
        instructions["instructions"]["apis"]["linz"]["key"] = linz_api_key
    catchment_boundary = dem_metadata_in_db.get_catchment_boundary(instructions)
    resolution = instructions["instructions"]["output"]["grid_params"]["resolution"]
    # Saving the outputs after each `outputtimestep` seconds
    output_timestep = 100.0
    # Saving the outputs till `endtime` number of seconds (or the output after `endtime` seconds
    # is the last one)
    end_time = 900.0
    run_model(
        bg_path=bg_path,
        instructions=instructions,
        catchment_boundary=catchment_boundary,
        resolution=resolution,
        end_time=end_time,
        output_timestep=output_timestep,
        rain_input_type="varying",
        engine=engine
    )


if __name__ == "__main__":
    main()
