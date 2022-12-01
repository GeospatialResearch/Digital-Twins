# -*- coding: utf-8 -*-
"""
Created on Tue Oct 18 16:30:21 2022.

@author: alo78
         xander.cai@pg.canterbury.ac.nz

Used to get the sea level rise predictions (several predictions options to choose from)
for site closest to the chosen latitude & longitude (Anywhere on the NZ Coastline) point
from the csv's downloaded from: https://searise.takiwa.co/.
"""

import pandas as pd
import geopandas as gpd
from haversine import haversine
import os
from shapely.geometry import Polygon
from src.digitaltwin import setup_environment


def gen_dataframe(file_path: str) -> pd.DataFrame:
    """ read csv file from input directory."""
    df_list = []
    for filename in os.listdir(file_path):
        if filename.endswith('.csv'):
            try:
                #  pyarrow is faster, need Pandas 1.4, released in January 2022
                df = pd.read_csv(file_path + filename, engine='pyarrow', dtype={'siteId': int})
                print('LOADED CSV file with pyarrow: ', filename)
            except (Exception, ):
                df = pd.read_csv(file_path + filename, dtype={'siteId': int})
                print('LOADED CSV file: ', filename)
            df["Region"] = filename[24:-4]
            df_list.append(df)
    return pd.concat(df_list, ignore_index=True, axis=0)


def get_nearest_coordinate(df: pd.DataFrame, target: tuple) -> tuple:
    """ find the nearest coordinate to target position in the input dataframe."""
    # get unique coordinate
    df_site = df.copy()[['lat', 'lon']].drop_duplicates(subset=['lat', 'lon'])
    # protect input boundary for haversine function
    assert -90 <= target[0] <= 90, "Latitude is out of range [-90, 90]"
    assert -180 <= target[0] <= 180, "Longitude is out of range [-180, 180]"
    # calculate distance from target coordinate
    df_site['distance'] = df_site.apply(lambda x: (haversine(target, (x['lat'], x['lon']))), axis=1)
    # sort by distance
    df_site = df_site.sort_values(by=['distance'], ascending=True).reset_index(drop=True)
    print("Nearest coordinates: ({}, {})".format(df_site.iloc[0]['lat'], df_site.iloc[0]['lon']))
    return df_site.iloc[0]['lat'], df_site.iloc[0]['lon']


def gen_slr_data(df: pd.DataFrame, target: tuple, crs: str = "epsg:2193") -> gpd.GeoDataFrame:
    """ generate geopandas dataframe that the coordinate is equal to target position."""
    # filter the coordinates based on target coordinate.
    df = df.loc[(df['lat'] == target[0]) & (df['lon'] == target[1])]
    # convert to geopandas dataframe from pandas dataframe
    gdf = gpd.GeoDataFrame(df, crs=crs, geometry=gpd.points_from_xy(df.lon, df.lat))
    gdf.rename(columns={'siteId': 'Site_ID', 'year': 'Projected_Year',
                        'p17': 'SLR_p17_confidence_interval_meters',
                        'p50': 'SLR_p50_confidence_interval_meters',
                        'p83': 'SLR_p83_confidence_interval_meters',
                        'lon': 'Longitude', 'lat': 'Latitude',
                        'measurementName': 'Scenario_(VLM_with_confidence)', },
               inplace=True)
    return gdf


def save_to_database(connect, gdf: gpd.GeoDataFrame, table_name: str, if_exists: str = 'replace'):
    """ save dataframe to database """
    gdf.to_postgis(table_name, connect, index=False, if_exists=if_exists)


def main():

    engine = setup_environment.get_database()

    path = "./data/"

    # Fetching centroid co-ordinate from user selected shapely polygon
    example_polygon_centroid = Polygon([[-43.298137, 172.568351], [-43.279144, 172.833569],
                                        [-43.418953, 172.826698], [-43.407542, 172.536636]]).centroid
    lat, long = example_polygon_centroid.coords[0]

    # start process
    slr_df = gen_dataframe(path)
    lat, long = get_nearest_coordinate(slr_df, (lat, long))
    slr_gdf = gen_slr_data(slr_df, (lat, long))
    save_to_database(engine, slr_gdf, 'sea_level_rise')
    # end process

    print(slr_gdf)


if __name__ == "__main__":
    main()
