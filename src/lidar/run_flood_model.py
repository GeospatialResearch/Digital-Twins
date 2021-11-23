# -*- coding: utf-8 -*-
"""
Created on Wed Nov 17 12:46:45 2021.

@author: pkh35
"""

import pathlib
import sys
import json
import xarray as xr
from datetime import datetime
import subprocess
import os
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String
from geoalchemy2 import Geometry
from sqlalchemy.orm import sessionmaker
import geopandas as gpd
from sqlalchemy import DateTime
from src.digitaltwin import setup_environment
from src.lidar import dem_metadata_in_db

Base = declarative_base()


def flood_model_inputs(bg_path, dem_path,instructions, endtime, outputtimestep, mask=15, gpudevice=0, smallnc=0):
    """Set parameters to run the flood model."""
    now = datetime.now()
    dt_string = now.strftime("%d_%m_%Y_%H_%M_%S")
    with xr.open_dataset(dem_path) as file_nc:
        max_temp_xr = file_nc
    keys = max_temp_xr.data_vars.keys()
    elev_var = list(keys)[0]
    dx = instructions['instructions']['output']['grid_params']['resolution']
    river = 'RiverDis.txt'
    extents = '1575386.285,1575387.285,5197749.557,5197750.557'
    outfile = rf'P:\Data\output_{dt_string}.nc'
    file = bg_flood_path(bg_path)
    try:
        with open(rf"{file}\BG_param.txt", "w+") as file:
            file.write(f"topo = {dem_path}?{elev_var};\n")
            file.write(f"gpudevice = {gpudevice};\nmask = {mask};\ndx = {dx};\n")
            file.write(f"smallnc = {smallnc};\n")
            file.write(f"outputtimestep = {outputtimestep};\nendtime = {endtime};\n")
            file.write(f"river = {river},{extents};\noutfile = {outfile};")
    except Exception as error:
        print(error, type(error))
        sys.exit()
    model_ouput_to_db(outfile, instructions)


def river_discharge_info(file):
    """Get the river discharge info. from design hydrographs."""
    with open(rf"{file}\RiverDis.txt") as file:
        print(file.read())


def bg_flood_path(file):
    """Check if the flood_model path exists."""
    file = pathlib.Path(file)
    if file.exists():
        return file
    else:
        print("directory doesn't exist")
        sys.exit()


def model_ouput_to_db(outfile, instructions):
    """Store metadata of model ouput in database."""
    engine = setup_environment.get_database()
    BGDEM.__table__.create(bind=engine, checkfirst=True)
    filepath = outfile
    filename = os.path.basename(filepath)
    catchment_boundary = gpd.read_file(
        instructions['instructions']['data_paths']['catchment_boundary'])
    geometry = str(catchment_boundary['geometry'][0])
    flood_dem = BGDEM(filepath=filepath, Filename=filename, geometry=geometry)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(flood_dem)
    session.commit()


class BGDEM(Base):
    """Create lidar table in the database."""

    __tablename__ = 'model_ouput_dem'
    unique_id = Column(Integer, primary_key=True, autoincrement=True)
    filepath = Column(String)
    Filename = Column(String)
    access_date = Column(DateTime, default=datetime.now())
    geometry = Column(Geometry('POLYGON'))


def main():
    """Call the functions."""
    with open(r'src\file.json', 'r') as file_pointer:
        instructions = json.load(file_pointer)
    dem_path = dem_metadata_in_db.get_dem_path(instructions)
    # Saving the outputs after each 100 seconds
    outputtimestep = 100.0
    # Saving the outputs till 14400 seconds (or the output after 14400 seconds is the last one)
    endtime = 900.0
    # visualising all the values larger than 15
    # mask = 15
    # using the gpu (if no gpu type -1)
    # gpudevice = 0
    # Level of refinement to apply to dx based on the adaptive resolution trigger
    # smallnc = 0
    bg_path = r'P:\BG-Flood_Win10_v0.6-a'
    flood_model_inputs(bg_path, dem_path, instructions, endtime, outputtimestep)
    river_discharge_info(bg_path)
    os.chdir(rf'{bg_path}')
    subprocess.call([rf"{bg_path}\BG_Flood_Cleanup.exe"])


if __name__ == '__main__':
    main()
