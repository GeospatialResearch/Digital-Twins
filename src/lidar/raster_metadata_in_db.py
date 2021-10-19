# -*- coding: utf-8 -*-
"""
Created on Tue Oct 12 13:29:01 2021.

@author: pkh35
"""

import pdal
import json
import os
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String
from geoalchemy2 import Geometry
from sqlalchemy.orm import sessionmaker
from src.digitaltwin import setup_environment

engine = setup_environment.get_database()
Base = declarative_base()


class Raster(Base):
    """Create raster table in the database."""

    __tablename__ = 'raster'
    unique_id = Column(Integer, primary_key=True, autoincrement=True)
    filepath = Column(String)
    filename = Column(String)
    filename_no_format = Column(String)
    geometry = Column(Geometry('POLYGON'))


engine = setup_environment.get_database()
Raster.__table__.create(engine, checkfirst=True)


def pointcloud_to_raster():
    """Point cloud data is converted to tiff files.

    Then tif files metadata is stored in the raster table in database.
    """
    filepaths = engine.execute(
        'SELECT t."Filename", l.filepath FROM tileindex t INNER JOIN lidar l ON t."Filename" = l.filename')

    filepaths = filepaths.fetchall()

    for i in range(len(filepaths)):
        filename = filepaths[i][0]
        filepath = filepaths[i][1]
        filename = filename.replace(".laz", ".tif")
        if os.path.isfile(filename):
            print(filename, "File exists")
        else:
            json2 = {
                "pipeline": [
                    {
                        "filename": "",
                        "gdaldriver": "GTiff",
                        "output_type": "all",
                        "resolution": "1.0",
                        "type": "writers.gdal"
                    }
                ]
            }

            json2['pipeline'][0]["filename"] = filename
            json2['pipeline'].insert(0, f'{filepath}')
            pipeline = pdal.Pipeline(json.dumps(json2))
            pipeline.validate()
            pipeline.execute()
            pipeline.arrays[0]


def raster_to_db():
    """Store metadata of converted tiff file in database."""
    tif_list = lidar_metadata_in_db.get_files(".tif")
    for file in tif_list:
        file_name = os.path.basename(file)
        file_name = file_name.replace("'", "")
        file_name_no_format = file_name.rsplit('.', 1)[0]
        raster = Raster(filepath=file, filename=file_name,
                        filename_no_format=file_name_no_format)
        Session = sessionmaker(bind=engine)
        session = Session()
        session.add(raster)
        session.commit()
        query = 'UPDATE raster SET geometry =(SELECT geometry FROM lidar WHERE lidar.filename_no_format = raster.filename_no_format)'
        engine.execute(query)


if __name__ == "__main__":
    import lidar_metadata_in_db
    raster_to_db()
