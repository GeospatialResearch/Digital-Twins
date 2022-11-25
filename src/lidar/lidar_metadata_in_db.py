# -*- coding: utf-8 -*-
"""
Created on Tue Oct  5 16:34:48 2021.

@author: pkh35
"""

import geoapis.lidar
import json
import geopandas as gpd
import os
import pathlib
import numpy as np
import pandas as pd
import zipfile
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String
from geoalchemy2 import Geometry
from sqlalchemy.orm import sessionmaker
import logging
import psycopg2
from src.digitaltwin import setup_environment

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)

Base = declarative_base()


class Lidar(Base):
    """Class used to create lidar table in the database."""
    __tablename__ = "lidar"
    unique_id = Column(Integer, primary_key=True, autoincrement=True)
    file_path = Column(String)
    file_name = Column(String)
    file_name_without_extension = Column(String)


def get_lidar_data(file_path_to_store, geometry_df):
    """Download the LiDAR data within the catchment area from opentopography
    using geoapis.
    https://github.com/niwa/geoapis
    """
    geometry_df.set_crs(crs="epsg:2193", inplace=True)
    lidar_fetcher = geoapis.lidar.OpenTopography(
        cache_path=file_path_to_store, search_polygon=geometry_df, verbose=True
    )
    lidar_fetcher.run()


def get_files(filetype, file_path_to_store):
    """To get the path of the downloaded point cloud files."""
    files_list = []
    files_path = []
    for (path, _dirs, files) in os.walk(file_path_to_store):
        for file in files:
            if file.endswith(filetype):
                files_list.append(os.path.join(path, file))
    for filepath in files_list:
        filepath = filepath.replace(os.sep, "/")
        files_path.append(filepath)
    return files_path


def remove_duplicate_rows(engine, table_name, column_name):
    """
    Remove rows from the table based on a column and add unique_id column in table if it is not exist.
    """
    engine.execute(
        f'ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS unique_id SERIAL PRIMARY KEY;'
    )
    engine.execute(
        f'DELETE FROM {table_name} a USING {table_name} b \
        WHERE a.unique_id < b.unique_id AND a."{column_name}" = b."{column_name}";'
    )


def store_lidar_path(engine, file_path_to_store, instruction_file, filetype=".laz"):
    """To store the path of downloaded point cloud files."""
    get_lidar_data(file_path_to_store, instruction_file)
    laz_files = get_files(filetype, file_path_to_store)
    for filepath in laz_files:
        file_name = os.path.basename(filepath)
        file_name_without_extension = file_name.rsplit(".", 1)[0]
        lidar = Lidar(
            file_path=filepath,
            file_name=file_name,
            file_name_without_extension=file_name_without_extension
        )
        Session = sessionmaker(bind=engine)
        session = Session()
        session.add(lidar)
        session.commit()
        remove_duplicate_rows(engine, "lidar", "file_name")


def gen_tileindex_name(dataframe_in,
                       columns_2d=['Filename', 'MinX', 'MinY', 'MaxX', 'MaxY', 'URL', 'geometry'],
                       columns_3d=['file_name', 'version', 'num_points', 'point_type', 'point_size',
                                   'min_x', 'max_x', 'min_y', 'max_y', 'min_z', 'max_z', 'URL', 'geometry'],
                       table_name=['tileindex2d', 'tileindex3d'],
                       column_name=['Filename', 'file_name']
                       ):
    """
    check the input dataframe column names,
    if input dataframe columns match columns_2d, output table_name[0] and column_name[0]
    if input dataframe columns match columns_3d, output table_name[1] and column_name[1]
    return output
    """
    table_name_out = ''
    column_name_out = ''
    columns_in = dataframe_in.columns.tolist()
    # for match case
    class Dims:
        dim2 = columns_2d
        dim3 = columns_3d
    match columns_in:  # Python 3.10 or above
        case Dims.dim2:
            table_name_out = table_name[0]
            column_name_out = column_name[0]
        case Dims.dim3:
            table_name_out = table_name[1]
            column_name_out = column_name[1]
        case _:
            log.debug(f"Input dataframe is not compatible. column names {columns_in}")
    return table_name_out, column_name_out


def store_tileindex(engine: object, file_path_to_store: object, filetype: object = ".shp") -> object:
    """Store tile information of each point in the point cloud data.
    Function extracts the zip files where tile index files are stored as shape files,
    then shapes files are stored in the database.
    """
    zip_files = []
    for (paths, _dirs, files) in os.walk(file_path_to_store):
        for file in files:
            if file.endswith(".zip"):
                zip_files.append(os.path.join(paths, file))
    # create tileindex table
    for file in zip_files:
        zip_file = zipfile.ZipFile(file)
        zip_file.extractall(file_path_to_store)
    shp_files = get_files(filetype, file_path_to_store)
    for file in shp_files:
        gdf = gpd.read_file(file)
        table_name, file_name = gen_tileindex_name(gdf)
        gdf.to_postgis(table_name, engine, index=False, if_exists="append")
        remove_duplicate_rows(engine, table_name, file_name)


def get_lidar_path(engine, geometry_df):
    """Get the file path within the catchment area."""
    poly = geometry_df["geometry"][0]
    query = f"select * from lidar where ST_Intersects(geometry, ST_GeomFromText('{poly}', 2193))"
    output_data = pd.read_sql_query(query, engine)
    pd.set_option("display.max_colwidth", None)
    return output_data["filepath"]


def main():
    engine = setup_environment.get_database()
    Lidar.__table__.create(bind=engine, checkfirst=True)
    file_path_to_store = pathlib.Path(r"../LiDAR/lidar_data")
    instruction_file = pathlib.Path("src/lidar/instructions_lidar.json")
    with open(instruction_file, "r") as file_pointer:
        instructions = json.load(file_pointer)
    geometry_df = gpd.GeoDataFrame.from_features(instructions["features"])
    store_lidar_path(engine, file_path_to_store, geometry_df)
    store_tileindex(engine, file_path_to_store)


if __name__ == "__main__":
    main()
