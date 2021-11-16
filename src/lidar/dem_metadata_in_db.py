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
from digitaltwin import setup_environment
import json
import os
import geopandas as gpd

Base = declarative_base()


class DEM(Base):
    """Create lidar table in the database."""

    __tablename__ = 'hydrological_dem'
    unique_id = Column(Integer, primary_key=True, autoincrement=True)
    filepath = Column(String)
    Filename = Column(String)
    geometry = Column(Geometry('POLYGON'))


def check_dem_exist(instructions, engine):
    """Only generate DEM if it doesn't exist in the database."""
    catchment_boundary = gpd.read_file(
        instructions['instructions']['data_paths']['catchment_boundary'])
    geometry = str(catchment_boundary['geometry'][0])
    query = f"select exists (Select 1 from hydrological_dem h where h.geometry ='{geometry}')"
    row = engine.execute(query)
    return row.fetchone()[0]


def dem_metadata_to_db(instructions, engine):
    """Store metadata of the generated DEM in database."""
    DEM.__table__.create(bind=engine, checkfirst=True)
    filepath = instructions['instructions']['data_paths']['result_dem']
    filename = os.path.basename(filepath)
    catchment_boundary = gpd.read_file(
        instructions['instructions']['data_paths']['catchment_boundary'])
    geometry = str(catchment_boundary['geometry'][0])
    lidar = DEM(filepath=filepath, Filename=filename, geometry=geometry)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(lidar)
    session.commit()


def dem_metadata_from_db(instructions, engine):
    """Get requested dem information from the database."""
    catchment_boundary = gpd.read_file(
        instructions['instructions']['data_paths']['catchment_boundary'])
    geometry = str(catchment_boundary['geometry'][0])
    query = f"SELECT filepath FROM hydrological_dem h where h.geometry = '{geometry}'"
    dem = engine.execute(query)
    return dem.fetchone()[0]


def main():
    """Call the functions."""
    with open(r'file.json', 'r') as file_pointer:
        instructions = json.load(file_pointer)

    engine = setup_environment.get_database()
    if check_dem_exist(instructions, engine) is False:
        try:
            runner = geofabrics.processor.DemGenerator(instructions)
            runner.run()
            dem_metadata_to_db(instructions, engine)
        except Exception as error:
            print(error, type(error))
    else:
        print('DEM exist in the database')
        dem_filepath = dem_metadata_from_db(instructions, engine)
        print(dem_filepath)


if __name__ == '__main__':
    main()
