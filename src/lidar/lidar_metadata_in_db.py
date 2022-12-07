# -*- coding: utf-8 -*-
"""
Created on Tue Oct  5 16:34:48 2021.

@author: pkh35
         xander.cai@pg.canterbury.ac.nz
"""

from typing import Union
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


def get_region_of_interest(instruction_file: str, crs: str = 'epsg:2193') -> gpd.GeoDataFrame:
    """ convert json instruction to geodataframe data type."""
    with open(instruction_file, "r") as file_pointer:
        instructions = json.load(file_pointer)
    gdf_interest = gpd.GeoDataFrame.from_features(instructions["features"])
    gdf_interest.set_crs(crs=crs, inplace=True)
    return gdf_interest


def get_lidar_data(file_path_to_store: str, instruction_file: str):
    """
    Download the LiDAR data within the catchment area from opentopography using geoapis.
    https://github.com/niwa/geoapis
    """
    gdf_interest = get_region_of_interest(instruction_file)
    lidar_fetcher = geoapis.lidar.OpenTopography(
        cache_path=file_path_to_store, search_polygon=gdf_interest, verbose=True
    )
    lidar_fetcher.run()


def get_files(filetype: str, file_path: str, expect: int = -1) -> Union[list, str, object]:
    """ To get the path of all the files with filetype extension in the input file path. """
    file_path_list = []
    for (path, _, files) in os.walk(file_path):
        for file in files:
            if file.endswith(filetype):
                file_path_list.append(os.path.normpath(os.path.join(path, file)))
    if expect < 0 or 1 < expect == len(file_path_list):
        return file_path_list
    elif expect == 1 and len(file_path_list) == 1:
        return file_path_list[0]
    else:
        log.debug(f"Error:: Find {len(file_path_list)} {filetype} files in {file_path}, where expect {expect}.")
        return None


def remove_duplicate_rows(engine: object, table_name: str, column_1: str, column_2: str):
    """ Remove rows from the table based on a column and add id column in table if it is not exist. """
    # add tbl_id column in each table if not exists
    engine.execute(
        f'ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS id SERIAL PRIMARY KEY;'
    )
    # delete duplicate rows from the newly created tables if exists
    engine.execute(
        f'DELETE FROM {table_name} a USING {table_name} b \
        WHERE a.id < b.id AND a."{column_1}" = b."{column_1}" AND a."{column_2}" = b."{column_2}";'
    )


def gen_tile_name(df: Union[pd.DataFrame, gpd.GeoDataFrame]) -> tuple:
    """
    check the input dataframe column names,
    if input dataframe columns match columns_2d, return output table_name[0] and column_name[0]
    if input dataframe columns match columns_3d, return output table_name[1] and column_name[1]
    """
    columns_3d = ['file_name', 'version', 'num_points', 'point_type', 'point_size',
                  'min_x', 'max_x', 'min_y', 'max_y', 'min_z', 'max_z', 'URL', 'geometry']
    columns_2d = ['Filename', 'MinX', 'MinY', 'MaxX', 'MaxY', 'URL', 'geometry']
    columns_in = df.columns.tolist()
    if columns_in == columns_2d:
        return 'tile_index_2d', 'Filename'
    elif columns_in == columns_3d:
        return 'tile_index_3d', 'file_name'
    else:
        log.debug(f"Error:: Invalid column name: {columns_in}.")


def drop_z(ds: gpd.GeoSeries) -> gpd.GeoSeries:
    """
    Drop Z coordinates from GeoSeries, returns GeoSeries
    Requires pygeos to be installed, otherwise it get error without warning.
    source: https://gist.github.com/rmania/8c88377a5c902dfbc134795a7af538d8
    """
    return gpd.GeoSeries.from_wkb(ds.to_wkb(output_dimension=2))


def gen_tile_to_lidar_data(gdf_tile: gpd.GeoDataFrame, crs: str = 'epsg:2193') -> gpd.GeoDataFrame:
    """
    generate geodataframe for lidar table, get file name and geometry from .shp tile file.
    if geometry in .shp tile file is polygon Z (3d: x, y, z), then convert it to polygon (2d: x, y).
    """
    gdf_to_lidar = gpd.GeoDataFrame()
    gdf_to_lidar['file_name'] = gdf_tile[gdf_tile.columns[0]].copy()
    if gdf_tile['geometry'][0].has_z:
        gdf_to_lidar['has_z'] = True
        # convert 3d to 2d polygon, pygeos package must be installed.
        gdf_to_lidar['geometry'] = drop_z(gdf_tile['geometry'].copy())
        gdf_to_lidar.set_crs(crs=crs, inplace=True)
    else:
        gdf_to_lidar['has_z'] = False
        gdf_to_lidar['geometry'] = gdf_tile['geometry'].copy()
    gdf_to_lidar['dataset'] = gdf_tile['dataset'].copy()
    return gdf_to_lidar


def store_tile_data(engine: object, file_path: str) -> gpd.GeoDataFrame:
    """
    Store tile information of each point in the point cloud data.
    Function extracts the zip files where tile index files are stored as shape files,
    then shapes files are stored in the database, and feed geometry info to lidar database.
    """
    zip_file = get_files('.zip', file_path, expect=1)
    zip_path = os.path.dirname(zip_file)
    dataset_name = os.path.basename(zip_path)
    with zipfile.ZipFile(zip_file, 'r') as zip_ref:
        zip_ref.extractall(zip_path)
    gdf = gpd.read_file(get_files('.shp', zip_path, expect=1))
    table_name, column_name = gen_tile_name(gdf)
    # add dataset column in tile index table to avoid duplicated file name issue.
    gdf['dataset'] = pd.Series(dataset_name).repeat(len(gdf)).reset_index(drop=True)
    gdf.to_postgis(table_name, engine, index=False, if_exists="append")
    remove_duplicate_rows(engine, table_name, column_name, "dataset")
    return gen_tile_to_lidar_data(gdf)


def store_lidar_data(engine: object, file_path: str, gdf_tile: gpd.GeoDataFrame) -> int:
    """ To store the path of downloaded point cloud files with geometry annotation. """
    file_path_list = get_files('.laz', file_path)
    file_name_list = [os.path.basename(file_path) for file_path in file_path_list]
    df = pd.DataFrame({'file_name': file_name_list,
                       'file_path': file_path_list})
    # remove not exist .laz row in the tile gdf.
    gdf = gdf_tile.merge(df, on='file_name', how='right')
    gdf.to_postgis('lidar', engine, index=False, if_exists="append")
    remove_duplicate_rows(engine, "lidar", "file_name", "file_path")
    return gdf['file_path'].nunique()


def store_tile_lidar_data(engin: object, data_path: str):
    """ store tile index and lidar data into database. """
    count = 0
    # load and save data based on directories can avoid duplicated .laz file name issue.
    for directory in os.listdir(data_path):
        file_path = os.path.join(data_path, directory)
        if os.path.isdir(file_path):
            gdf_tile_to_lidar = store_tile_data(engin, file_path)
            count += store_lidar_data(engin, file_path, gdf_tile_to_lidar)
    # check .laz file number, which should match the .laz number in lidar database.
    file_path_list = get_files('.laz', data_path)
    assert len(file_path_list) == count, \
        f"Error:: download .laz file number {len(file_path_list)} is different with database {count}."
    log.debug(f"Info:: Find total {len(file_path_list)} .laz files in {data_path}.")
    log.debug(f'Info:: Store total {count} .laz file with tile index geometry in "lidar" database.')


def retrieve_lidar_data(engine: object, instruction_file: str) -> gpd.GeoDataFrame:
    """Get the file path within the catchment area."""
    gdf_interest = get_region_of_interest(instruction_file)
    poly = gdf_interest["geometry"][0]
    query = f"select * from lidar where ST_Intersects(geometry, ST_GeomFromText('{poly}', 2193))"
    gdf = gpd.GeoDataFrame.from_postgis(query, engine, geom_col='geometry')
    gdf.drop(columns=gdf.columns[-1], inplace=True)
    return gdf


def main():
    # input
    data_path = str(pathlib.Path(r"../LiDAR/lidar_data"))
    instruction_file = str(pathlib.Path(r"./src/lidar/instructions_lidar.json"))
    engine = setup_environment.get_database()

    # set up or update database
    get_lidar_data(data_path, instruction_file)
    store_tile_lidar_data(engine, data_path)

    # use database
    gdf_retrieve = retrieve_lidar_data(engine, instruction_file)
    log.debug(f"Info:: Retrieved total {gdf_retrieve['file_path'].nunique()} .laz files in the region of interest.")

    # verify .laz file is equal in local and database
    list_local = get_files('.laz', data_path)
    list_local.sort()
    list_db = gdf_retrieve['file_path'].sort_values().to_list()
    log.debug(f"Info:: Is local .laz file path exactly equal to lidar database? {list_local==list_db}")

    # display retrieved dataframe
    pd.set_option('display.max_columns', None)
    print(gdf_retrieve)


if __name__ == "__main__":
    main()
