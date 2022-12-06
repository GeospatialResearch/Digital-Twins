# -*- coding: utf-8 -*-
"""
Created on Tue Oct  5 16:34:48 2021.

@author: pkh35
         xander.cai@pg.canterbury.ac.nz
"""

import collections
import geoapis.lidar
import json
import geopandas as gpd
import os
import pathlib
import pandas as pd
import zipfile
import logging
from src.digitaltwin import setup_environment

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
log.addHandler(stream_handler)


def get_lidar_data(file_path_to_store: str, region_of_interest: gpd.GeoDataFrame):
    """
    Download the LiDAR data within the catchment area from opentopography using geoapis.
    https://github.com/niwa/geoapis
    """
    region_of_interest.set_crs(crs="epsg:2193", inplace=True)
    lidar_fetcher = geoapis.lidar.OpenTopography(
        cache_path=file_path_to_store, search_polygon=region_of_interest, verbose=True
    )
    lidar_fetcher.run()


def get_files(filetype: str, file_path: str, expect: int = -1) -> list:
    """ To get the path of all the files with filetype extension in the input file path. """
    file_path_list = []
    for (path, _, files) in os.walk(file_path):
        for file in files:
            if file.endswith(filetype):
                file_path_list.append(os.path.join(path, file))
    if 0 < expect != len(file_path_list):
        log.debug(f"Error:: Find {len(file_path_list)} {filetype} files in {file_path}, while expect {expect}.")
    return [file_path.replace(os.sep, "/") for file_path in file_path_list]


def remove_duplicate_rows(engine: object, table_name: str, column_1: str, column_2: str):
    """ Remove rows from the table based on a column and add unique_id column in table if it is not exist. """
    # add tbl_id column in each table if not exists
    engine.execute(
        f'ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS id SERIAL PRIMARY KEY;'
    )
    # delete duplicate rows from the newly created tables if exists
    engine.execute(
        f'DELETE FROM {table_name} a USING {table_name} b \
        WHERE a.id < b.id AND a."{column_1}" = b."{column_1}" AND a."{column_2}" = b."{column_2}";'
    )


def gen_tile_name(df: object,
                  columns_2d: list = ['Filename', 'MinX', 'MinY', 'MaxX', 'MaxY', 'URL', 'geometry'],
                  columns_3d: list = ['file_name', 'version', 'num_points', 'point_type', 'point_size',
                                      'min_x', 'max_x', 'min_y', 'max_y', 'min_z', 'max_z', 'URL', 'geometry'],
                  table_name: list = ['tile_index_2d', 'tile_index_3d'],
                  column_name: list = ['Filename', 'file_name']
                  ) -> tuple:
    """
    check the input dataframe column names,
    if input dataframe columns match columns_2d, output table_name[0] and column_name[0]
    if input dataframe columns match columns_3d, output table_name[1] and column_name[1]
    return output
    """
    columns_in = df.columns.tolist()
    if columns_in == columns_2d:
        return table_name[0], column_name[0]
    elif columns_in == columns_3d:
        return table_name[1], column_name[1]
    else:
        log.debug(f"Error:: Invalid column name: {columns_in}.")


def drop_z(ds: gpd.GeoSeries) -> gpd.GeoSeries:
    """
    Drop Z coordinates from GeoSeries, returns GeoSeries
    Requires pygeos to be installed, otherwise it get error without warning.
    source: https://gist.github.com/rmania/8c88377a5c902dfbc134795a7af538d8
    """
    return gpd.GeoSeries.from_wkb(ds.to_wkb(output_dimension=2))


def gen_tile_to_lidar_data(gdf_tile: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    generate geodataframe for lidar table, get file name and geometry from .shp tile file.
    if geometry in .shp tile file is polygon Z (3d: x, y, z), then convert it to polygon (2d: x, y).
    """
    gdf_to_lidar = gpd.GeoDataFrame()
    gdf_to_lidar['file_name'] = gdf_tile[gdf_tile.columns[0]].copy()
    if gdf_tile['geometry'][0].has_z:
        gdf_to_lidar['has_z'] = True
        # convert 3d to 2d polygon
        gdf_to_lidar['geometry'] = drop_z(gdf_tile['geometry'].copy())
    else:
        gdf_to_lidar['has_z'] = False
        gdf_to_lidar['geometry'] = gdf_tile['geometry'].copy()
    gdf_to_lidar.set_crs(crs="epsg:2193", inplace=True)
    return gdf_to_lidar


def store_tile(engine: object, file_path: str) -> gpd.GeoDataFrame:
    """
    Store tile information of each point in the point cloud data.
    Function extracts the zip files where tile index files are stored as shape files,
    then shapes files are stored in the database, and feed geometry info to lidar database.
    """
    zip_file = get_files('.zip', file_path, 1)[0]
    with zipfile.ZipFile(zip_file, 'r') as zip_ref:
        zip_path = os.path.split(zip_file)[0]
        dataset = zip_path.split('/')[-1]
        zip_ref.extractall(zip_path)
        gdf = gpd.read_file(get_files('.shp', zip_path, 1)[0])
        table_name, column_name = gen_tile_name(gdf)
        gdf['dataset'] = pd.Series(dataset).repeat(len(gdf)).reset_index(drop=True)
        gdf.to_postgis(table_name, engine, index=False, if_exists="append")
        remove_duplicate_rows(engine, table_name, column_name, 'dataset')
        return gen_tile_to_lidar_data(gdf)


def store_lidar(engine: object, file_path: str, gdf_tile: gpd.GeoDataFrame) -> int:
    """ To store the path of downloaded point cloud files with geometry annotation. """
    file_path_list = get_files('.laz', file_path)
    file_name_list = [os.path.basename(file_path) for file_path in file_path_list]
    df = pd.DataFrame({'file_name': file_name_list,
                       'file_path': file_path_list})
    # remove not exist .laz row in the tile gdf.
    gdf = gdf_tile.merge(df, on='file_name', how='right')
    gdf.to_postgis('lidar', engine, index=False, if_exists="append")
    remove_duplicate_rows(engine, "lidar", "file_name", "file_path")
    return len(gdf)


def store_tile_lidar(engin: object, data_path: str):
    """ store tile index and lidar data into database. """
    count = 0
    for directory in os.listdir(data_path):
        file_path = os.path.join(data_path, directory)
        gdf_tile_to_lidar = store_tile(engin, file_path)
        count += store_lidar(engin, file_path, gdf_tile_to_lidar)
    # check .laz file number
    file_path_list = get_files('.laz', data_path)
    assert len(file_path_list) == count, \
        f"Error:: download .laz file number {len(file_path_list)} is different with database {count}."
    log.debug(f"Info:: Find {len(file_path_list)} .laz files in {data_path}.")
    log.debug(f"Info:: Store {count} .laz file with tile index geometry in database.")


def get_lidar_path(engine: object, region_of_interest: gpd.GeoDataFrame) -> list:
    """Get the file path within the catchment area."""
    poly = region_of_interest["geometry"][0]
    query = f"select * from lidar where ST_Intersects(geometry, ST_GeomFromText('{poly}', 2193))"
    output_data = pd.read_sql_query(query, engine)
    return output_data["file_path"].tolist()


def main():
    pd.set_option('display.max_columns', None)
    engine = setup_environment.get_database()
    data_path = pathlib.Path(r"../LiDAR/lidar_data")
    instruction_file = pathlib.Path(r"./src/lidar/instructions_lidar.json")
    with open(instruction_file, "r") as file_pointer:
        instructions = json.load(file_pointer)
    regin_of_interest = gpd.GeoDataFrame.from_features(instructions["features"])
    get_lidar_data(data_path, regin_of_interest)
    store_tile_lidar(engine, data_path)

    file_path = get_lidar_path(engine, regin_of_interest)
    log.debug(f"Info:: Retrieved total {len(file_path)} .laz files in the region of interest.")


if __name__ == "__main__":
    main()
