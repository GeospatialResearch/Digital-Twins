# -*- coding: utf-8 -*-
"""
Created on Wed Nov 10 13:22:27 2021.

@author: pkh35
"""

import geofabrics.processor
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String
from geoalchemy2 import Geometry
from sqlalchemy.orm import sessionmaker
import os
import geopandas as gpd
import sys
import pathlib

Base = declarative_base()


class DEM(Base):
    """Class used to create hydrological_dem table."""

    __tablename__ = "hydrological_dem"
    unique_id = Column(Integer, primary_key=True, autoincrement=True)
    filepath = Column(String)
    Filename = Column(String)
    geometry = Column(Geometry("POLYGON"))


def dem_table(engine):
    """Create hydrological_dem table if doesn't exists."""
    DEM.__table__.create(bind=engine, checkfirst=True)


def check_dem_exist(instructions, engine):
    """Only generate DEM if it doesn't exist in the database."""
    dem_table(engine)
    cache_path = pathlib.Path(instructions["instructions"]["data_paths"]["local_cache"])
    subfolder = instructions["instructions"]["data_paths"]["subfolder"]
    catchment_name = instructions["instructions"]["data_paths"]["catchment_boundary"]
    catchment_boundary = gpd.read_file(cache_path / subfolder / catchment_name)
    geometry = str(catchment_boundary["geometry"][0])
    query = (
        f"select exists (Select 1 from hydrological_dem where geometry ='{geometry}')"
    )
    row = engine.execute(query)
    return row.fetchone()[0]


def generate_dem(instructions):
    """Use geofabrics to generate the hydrologically conditioned DEM."""
    runner = geofabrics.processor.RawLidarDemGenerator(instructions["instructions"])
    runner.run()
    runner = geofabrics.processor.HydrologicDemGenerator(instructions["instructions"])
    runner.run()


def dem_metadata_to_db(instructions, engine):
    """Store metadata of the generated DEM in database."""
    filepath = instructions["instructions"]["data_paths"]["result_dem"]
    filename = os.path.basename(filepath)
    cache_path = pathlib.Path(instructions["instructions"]["data_paths"]["local_cache"])
    catchment_boundary_path = (
        cache_path
        / instructions["instructions"]["data_paths"]["subfolder"]
        / instructions["instructions"]["data_paths"]["catchment_boundary"]
    )
    catchment_boundary = gpd.read_file(catchment_boundary_path)
    geometry = str(catchment_boundary["geometry"][0])
    lidar = DEM(filepath=filepath, Filename=filename, geometry=geometry)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(lidar)
    session.commit()


def dem_metadata_from_db(instructions, engine):
    """Get requested dem information from the database."""
    cache_path = pathlib.Path(instructions["instructions"]["data_paths"]["local_cache"])
    catchment_boundary_path = (
        cache_path
        / instructions["instructions"]["data_paths"]["subfolder"]
        / instructions["instructions"]["data_paths"]["catchment_boundary"]
    )
    catchment_boundary = gpd.read_file(catchment_boundary_path)
    geometry = str(catchment_boundary["geometry"][0])
    query = f"SELECT filepath FROM hydrological_dem WHERE geometry = '{geometry}'"
    dem = engine.execute(query)
    return dem.fetchone()[0]


def get_dem_path(instructions, engine):
    """Pass dem information to other functions."""
    if check_dem_exist(instructions, engine) is False:
        try:
            generate_dem(instructions)
            dem_metadata_to_db(instructions, engine)
        except Exception as error:
            print(error, type(error))
            sys.exit()
    dem_filepath = dem_metadata_from_db(instructions, engine)
    return dem_filepath
