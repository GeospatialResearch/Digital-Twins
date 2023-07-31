# -*- coding: utf-8 -*-
"""
Created on Tue Oct  5 16:34:48 2021.

@author: pkh35
"""

import logging
import os
import pathlib
import zipfile

import geoapis.lidar
import geopandas as gpd
import numpy as np
import pandas as pd
import psycopg2
from geoalchemy2 import Geometry
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from src import config
from src.digitaltwin import setup_environment
from src.digitaltwin.utils import setup_logging

log = logging.getLogger(__name__)

Base = declarative_base()


class Lidar(Base):
    """Class used to create lidar table in the database."""

    __tablename__ = "lidar"
    unique_id = Column(Integer, primary_key=True, autoincrement=True)
    filepath = Column(String)
    Filename = Column(String)
    filename_no_format = Column(String)
    geometry = Column(Geometry("POLYGON"))


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


def remove_duplicate_rows(engine, table_name):
    """Remove duplicate rows from the tables."""
    # add tbl_id column in each table
    engine.execute(
        'ALTER TABLE "%(table_name)s" ADD COLUMN IF NOT EXISTS unique_id SERIAL PRIMARY KEY'
        % ({"table_name": table_name})
    )
    # delete duplicate rows from the newly created tables if exists
    engine.execute(
        'DELETE FROM "%(table_name)s" a USING "%(table_name)s" b\
                    WHERE a.unique_id < b.unique_id AND a."Filename" = b."Filename";'
        % ({"table_name": table_name})
    )


def store_lidar_path(engine, file_path_to_store, geometry_df, filetype=".laz"):
    """To store the path of downloaded point cloud files."""
    get_lidar_data(file_path_to_store, geometry_df)
    laz_files = get_files(filetype, file_path_to_store)
    for filepath in laz_files:
        file_name = os.path.basename(filepath)
        file_name_no_format = file_name.rsplit(".", 1)[0]
        lidar = Lidar(
            filepath=filepath,
            Filename=file_name,
            filename_no_format=file_name_no_format,
        )
        Session = sessionmaker(bind=engine)
        session = Session()
        session.add(lidar)
        session.commit()
        remove_duplicate_rows(engine, "lidar")


def store_tileindex(engine, file_path_to_store, filetype=".shp"):
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
    for i in zip_files:
        zip_file = zipfile.ZipFile(i)
        zip_file.extractall(file_path_to_store)
    shp_files = get_files(filetype, file_path_to_store)
    for i in shp_files:
        try:
            gdf = gpd.read_file(i)
            gdf.to_postgis("tileindex", engine, index=False, if_exists="append")
        except psycopg2.ProgrammingError as error:
            # TODO: if_exists=append does not allow for the addition of new
            # fields to a table, only new rows. NZ20_Canterbury have new columns
            # Fix in https://github.com/GeospatialResearch/Digital-Twins/issues/33
            filename = os.path.basename(i)
            query = "SELECT column_name FROM information_schema.columns WHERE table_name = 'tileindex'"
            col_names_in_db = pd.read_sql_query(query, engine)["column_name"].tolist()
            col_names_in_shp = gdf.columns.tolist()
            col_names_not_in_db = np.setdiff1d(col_names_in_shp, col_names_in_db)
            log.debug(f"{filename}: {error}. new column names: {col_names_not_in_db}")
    remove_duplicate_rows(engine, "tileindex")
    query = 'UPDATE lidar SET geometry = (SELECT geometry FROM tileindex WHERE tileindex."Filename" = lidar."Filename")'
    engine.execute(query)


def get_lidar_path(engine, geometry_df):
    """Get the file path within the catchment area."""
    poly = geometry_df["geometry"][0]
    query = f"select * from lidar where ST_Intersects(geometry, ST_GeomFromText('{poly}', 2193))"
    output_data = pd.read_sql_query(query, engine)
    pd.set_option("display.max_colwidth", None)
    return output_data["filepath"]


def main(selected_polygon_gdf: gpd.GeoDataFrame, log_level: int = logging.DEBUG) -> None:
    setup_logging(log_level)
    engine = setup_environment.get_database()
    Lidar.__table__.create(bind=engine, checkfirst=True)
    data_dir = config.get_env_variable("DATA_DIR")
    file_path_to_store = pathlib.Path(rf"{data_dir}/LiDAR")
    store_lidar_path(engine, file_path_to_store, selected_polygon_gdf)
    store_tileindex(engine, file_path_to_store)


if __name__ == "__main__":
    sample_polygon = gpd.GeoDataFrame.from_file("selected_polygon.geojson")
    main(sample_polygon)
