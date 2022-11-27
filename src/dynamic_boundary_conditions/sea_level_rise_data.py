# -*- coding: utf-8 -*-
"""
Created on Tue Oct 18 16:30:21 2022.

@author: alo78


Used to get the sea level rise predictions (several predictions options to choose from)
for site closest to the chosen latitude & longitude (Anywhere on the NZ Coastline) point
from the csv's downloaded from: https://searise.takiwa.co/.


"""

from datetime import date, datetime, timedelta
import pandas as pd
import geopandas as gpd
from haversine import haversine
import os
from shapely.geometry import Polygon, Point


def read_slr_files(path: str):
    """Reads in all the SLR data csv's downloaded from https://searise.takiwa.co/ into a pandas dataframe """
    sea_level_rise_projections_nz = pd.DataFrame()
    for filename in os.listdir(path):
        if filename.endswith('.csv'):
            sea_level_rise_projections_region = pd.read_csv(path + filename)
            sea_level_rise_projections_region["Region"] = filename[24:-4]
            print('LOADED: ', filename)

            sea_level_rise_projections_nz = pd.concat(
                [sea_level_rise_projections_nz, sea_level_rise_projections_region], ignore_index=True, axis=0)

    # Converting to Geopandas points
    print('Converting to Geopandas data frame with geometry...')
    sea_level_rise_projections_nz = gpd.GeoDataFrame(sea_level_rise_projections_nz,
                                                     geometry=gpd.points_from_xy(sea_level_rise_projections_nz.lon,
                                                                                 sea_level_rise_projections_nz.lat))

    sea_level_rise_projections_nz.rename(
        columns={'siteId': 'Site_ID', 'year': 'Projected_Year', 'p17': 'SLR_p17_confidence_interval_meters',
                 'p50': 'SLR_p50_confidence_interval_meters', 'p83': 'SLR_p83_confidence_interval_meters',
                 'lon': 'Longitude', 'lat': 'Latitude', 'measurementName': 'Scenario_(VLM_with_confidence)', },
        inplace=True)

    return sea_level_rise_projections_nz


def unique_locations(sea_level_rise_projections_nz: gpd.geodataframe.GeoDataFrame):
    """Finds the unique lat lon coordinates (site locations) and appends them to list and returns that list"""
    locations_lat_lon = []
    # Acquiring unique pairs
    unique_location = sea_level_rise_projections_nz.geometry.unique()
    # Adding pairs to list of dictionarys to map to later on
    print('Finding unique locations...')
    for i in unique_location:
        locations_value_pair = {'lat': i.y, 'lon': i.x}
        locations_lat_lon.append(locations_value_pair)
    return locations_lat_lon


def closest_site_location(locations_lat_lon: list, user_value: dict):
    """"Returns the haversine closest SLR site location"""
    return min(locations_lat_lon, key=lambda p: haversine((user_value['lat'], user_value['lon']), (p['lat'], p['lon'])))


def nearest_site(locations_lat_lon: list, lat_input: float, lon_input: float):
    """ Returns lat lon coordinates which is then used by site_data function
        Selecting only the data for chosen site (e.g. 4303 is site just south
        of Waimakiriri River Mouth which is closest to a selected location of
        ('lat': -43.391266, 'lon': 172.715979)"""

    user_value = {'lat': lat_input, 'lon': lon_input}
    site = closest_site_location(locations_lat_lon, user_value)
    print('Closest Site Location: ', str(site.get("lat")) + "," + str(site.get("lon")))
    print('Searching for site data: ')
    return Point(site.get("lon"), site.get("lat"))


def site_data(sea_level_rise_projections_nz: gpd.geodataframe.GeoDataFrame, locations_lat_lon: list, lat_input: float,
              lon_input: float):
    """ Returns data for closest site by querying user for their desired location (calls nearest_site function) """
    if lat_input < -90 or lat_input > 90:
        raise ValueError("Latitude is out of range [-90, 90]")
    if lon_input < -180 or lon_input > 180:
        raise ValueError("Longitude is out of range [-180, 180]")

    return sea_level_rise_projections_nz.loc[
        sea_level_rise_projections_nz['geometry'] == nearest_site(locations_lat_lon, lat_input, lon_input)]


def main():
    path = "data/"

    ## Fetching centroid co-ordinate from user selected shapely polygon
    lat = Polygon([[-43.298137, 172.568351], [-43.279144, 172.833569], [-43.418953, 172.826698],
                   [-43.407542, 172.536636]]).centroid.coords[0][0]
    long = Polygon([[-43.298137, 172.568351], [-43.279144, 172.833569], [-43.418953, 172.826698],
                    [-43.407542, 172.536636]]).centroid.coords[0][1]

    nz_SLR_data = read_slr_files(path)
    unique_location_pairs = unique_locations(nz_SLR_data)
    SLR_Site_Data = site_data(nz_SLR_data, unique_location_pairs, lat, long)
    print(SLR_Site_Data)


if __name__ == "__main__":
    main()
