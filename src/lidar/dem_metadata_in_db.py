# -*- coding: utf-8 -*-
"""
Created on Wed Nov 10 13:22:27 2021.

@author: pkh35
"""

import pathlib

import geofabrics.processor
import geopandas as gpd
from geoalchemy2 import Geometry
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

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


def check_dem_exist(selected_polygon: gpd.GeoDataFrame, engine):
    """Only generate DEM if it doesn't exist in the database."""
    dem_table(engine)
    geometry = str(selected_polygon["geometry"][0])
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


def dem_metadata_to_db(instructions, selected_polygon: gpd.GeoDataFrame, engine):
    """Store metadata of the generated DEM in database."""
    geometry = str(selected_polygon["geometry"][0])
    data_paths = instructions["instructions"]["data_paths"]
    cache_path = pathlib.Path(data_paths["local_cache"])
    subfolder = data_paths["subfolder"]
    result_dem_name = data_paths["result_dem"]
    result_dem_path = (cache_path / subfolder / result_dem_name).as_posix()
    lidar = DEM(filepath=result_dem_path, Filename=result_dem_name, geometry=geometry)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(lidar)
    session.commit()


def dem_metadata_from_db(selected_polygon: gpd.GeoDataFrame, engine):
    """Get requested dem information from the database."""
    geometry = str(selected_polygon["geometry"][0])
    query = f"SELECT filepath FROM hydrological_dem WHERE geometry = '{geometry}'"
    dem = engine.execute(query)
    return dem.fetchone()[0]


def get_dem_path(instructions, selected_polygon: gpd.GeoDataFrame, engine):
    """Pass dem information to other functions."""
    if not check_dem_exist(selected_polygon, engine):
        generate_dem(instructions)
        dem_metadata_to_db(instructions, selected_polygon, engine)
    dem_filepath = dem_metadata_from_db(selected_polygon, engine)
    return dem_filepath
