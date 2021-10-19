# -*- coding: utf-8 -*-
"""
Created on Tue Oct  5 16:34:48 2021.

@author: pkh35
"""

import geoapis.lidar
import json
import geopandas as gpd
import os
import zipfile
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String
from geoalchemy2 import Geometry
from sqlalchemy.orm import sessionmaker
from src.digitaltwin import setup_environment

Base = declarative_base()


class Lidar(Base):
    """Create lidar table in the database."""

    __tablename__ = 'lidar'
    unique_id = Column(Integer, primary_key=True, autoincrement=True)
    filepath = Column(String)
    filename = Column(String)
    filename_no_format = Column(String)
    geometry = Column(Geometry('POLYGON'))


engine = setup_environment.get_database()
Lidar.__table__.create(bind=engine, checkfirst=True)


def get_files(filetype, folder):
    """To get the path of the downloaded point cloud files."""
    file_list = []
    files_path = []
    for (paths, dirs, files) in os.walk(folder):
        for file in files:
            if file.endswith(filetype):
                file_list.append(os.path.join(paths, file))
    for filepath in file_list:
        filepath = filepath.replace(os.sep, '/')
        filepath = "'{}'".format(filepath)
        filepath = filepath.replace("'", "")
        files_path.append(filepath)
    return files_path


def store_lidar_path(filetype, folder):
    """To store the path of downloaded point cloud data."""
    laz_files = get_files(filetype, folder)
    for file in laz_files:
        file_name = os.path.basename(file)
        file_name = file_name.replace("'", "")
        file_name_no_format = file_name.rsplit('.', 1)[0]
        lidar = Lidar(filepath=file, filename=file_name,
                      filename_no_format=file_name_no_format)
        Session = sessionmaker(bind=engine)
        session = Session()
        session.add(lidar)
        session.commit()
        remove_duplicate_rows("lidar")


def remove_duplicate_rows(table_name):
    """Remove duplicate rows from the tables."""
    # add tbl_id column in each table
    engine.execute('ALTER TABLE \"%(table_name)s\" ADD COLUMN IF NOT EXISTS tbl_id SERIAL' % (
        {'table_name': table_name}))
    # delete duplicate rows from the newly created tables if exists
    engine.execute('DELETE FROM \"%(table_name)s\" a USING \"%(table_name)s\" b WHERE a.tbl_id < b.tbl_id AND a.filename = b.filename;' % (
        {'table_name': table_name}))


def store_tileindex(filetype, folder):
    """Store tile information of each point in the point cloud data.

    Function extracts the zip files where tile index files are stored as shape
    files, then shapes files are stored in the database
    """
    zip_files = []
    for (paths, dirs, files) in os.walk(folder):
        for file in files:
            if file.endswith(".zip"):
                zip_files.append(os.path.join(paths, file))
    # create tileindex table
    for i in zip_files:
        zip_file = zipfile.ZipFile(i)
        zip_file.extractall(folder)
    shp_files = get_files(filetype, folder)
    for i in shp_files:
        gdf = gpd.read_file(i)
        gdf.to_postgis("tileindex", engine, index=False, if_exists='append')
    remove_duplicate_rows("tileindex")
    query = 'UPDATE lidar SET geometry =(SELECT geometry FROM tileindex WHERE tileindex."Filename" = lidar.filename)'
    engine.execute(query)


if __name__ == "__main__":
    FILE_PATH = "lidar_test.json"
    with open(FILE_PATH, 'r') as file_pointer:
        instructions = json.load(file_pointer)
    geometry_df = gpd.GeoDataFrame.from_features(instructions["features"])
    geometry_df.set_crs(crs='epsg:2193', inplace=True)

    folder = "YOUR_PATH"
    lidar_fetcher = geoapis.lidar.OpenTopography(cache_path=folder,
                                                 search_polygon=geometry_df, verbose=True)
    lidar_fetcher.run()
    store_lidar_path(".laz", folder)
    store_tileindex(".shp", folder)
