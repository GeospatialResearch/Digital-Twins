# -*- coding: utf-8 -*-
"""
Created on Tue Oct 18 16:30:21 2022.

@author: alo78
"""

from datetime import date, datetime, timedelta
import pandas as pd
from haversine import haversine
import os

def read_slr_files(path):
    sea_level_rise_projections_nz = pd.DataFrame()
    for filename in os.listdir(path):
        if filename.endswith('.csv'):
            sea_level_rise_projections_region = pd.read_csv(path + filename)
            sea_level_rise_projections_region["Region"] = filename[24:-4]
            # Creating new column containing location pair
            sea_level_rise_projections_region['Location'] = sea_level_rise_projections_region[['lat', 'lon']].apply(
                lambda row: ','.join(row.values.astype(str)), axis=1)
            print('LOADED: ', filename)

            sea_level_rise_projections_nz = pd.concat(
                [sea_level_rise_projections_nz, sea_level_rise_projections_region], ignore_index=True, axis=0)

    sea_level_rise_projections_nz.rename(columns={'siteId':
                                                      'Site_ID',
                                                  'year': 'Projected_Year',
                                                  'p17': 'SLR_p17_confidence interval_meters',
                                                  'p50': 'SLR_p50_confidence interval_meters',
                                                  'p83': 'SLR_p83_confidence interval_meters',
                                                  'lon': 'Longitude',
                                                  'lat': 'Latitude',
                                                  'measurementName': 'Scenario_(VLM with confidence level)', }, inplace=True)

    return sea_level_rise_projections_nz





def unique_locations(sea_level_rise_projections_nz):
    locations_lat_lon = []
    # Acquiring unique pairs
    unique_location = sea_level_rise_projections_nz.Location.unique().astype(str)
    # Adding pairs to list of dictionarys to map to later on
    for i in unique_location:
        locations_value_pair = {'lat': float(i.split(',')[0]), 'lon': float(i.split(',')[1])}
        locations_lat_lon.append(locations_value_pair)
    return locations_lat_lon





def closest_site_location(data, v):
    return min(data, key=lambda p: haversine((v['lat'], v['lon']), (p['lat'], p['lon'])))



def nearest_site(locations_lat_lon, lat_input, lon_input):
    """ Returns lat lon coordinates which is then used by site_data function
        Selecting only the data for chosen site (e.g. 4303 is site just south
        of Waimakiriri River Mouth which is closest to a selected location of
        ('lat': -43.391266, 'lon': 172.715979)"""

    user_value = {'lat': lat_input, 'lon': lon_input}
    site = closest_site_location(locations_lat_lon, user_value)
    print(str(site.get("lat")) + "," + str(site.get("lon")))
    return str(site.get("lat")) + "," + str(site.get("lon"))



def site_data(sea_level_rise_projections_nz, locations_lat_lon, lat_input, lon_input):
    """ Returns data for closest site by querying user for their desired location (calls nearest_site function) """
    return sea_level_rise_projections_nz.loc[sea_level_rise_projections_nz['Location'] == nearest_site(locations_lat_lon, lat_input, lon_input)]




def main():
    path = "data/"

    # Lat and Long cooords of polygon centre
    lat_input = -43.391266
    lon_input = 172.715979

    nz_SLR_data = read_slr_files(path)
    unique_location_pairs = unique_locations(nz_SLR_data)
    SLR_Site_Data = site_data(nz_SLR_data, unique_location_pairs, lat_input, lon_input)
    print(SLR_Site_Data)



if __name__ == "__main__":
    main()