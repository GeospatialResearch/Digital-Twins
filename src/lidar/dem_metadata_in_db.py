# -*- coding: utf-8 -*-
"""
Created on Wed Nov 10 13:22:27 2021

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


engine = setup_environment.get_database()
DEM.__table__.create(bind=engine, checkfirst=True)

def main():
    with open(r'P:/Data/file.json', 'r') as file_pointer:
        instructions = json.load(file_pointer)
    filepath=instructions['instructions']['data_paths']['result_dem']
    filename=os.path.basename(filepath)
    catchmnet_boundary = gpd.read_file(instructions['instructions']['data_paths']['catchment_boundary'])
    geometry=str(catchmnet_boundary['geometry'][0])
    try:
        runner = geofabrics.processor.DemGenerator(instructions)
        runner.run()
        lidar = DEM(filepath=filepath, Filename=filename, geometry=geometry)
        Session = sessionmaker(bind=engine)
        session = Session()
        session.add(lidar)
        session.commit()
    except Exception as error:
        print(error, type(error))


if __name__ == '__main__':
    main()
