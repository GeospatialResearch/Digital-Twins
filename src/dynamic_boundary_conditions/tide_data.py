# -*- coding: utf-8 -*-
"""
Created on Tue Oct 18 16:30:21 2022.

@author: alo78



Used to get the tide model predictions for site closest to the chosen latitude & longitude (Anywhere on the NZ Coastline) point
from the API created by NIWA (https://developer.niwa.co.nz/docs/tide-api/1/overview). User can specify how many days of data is
required and how much data (in days) either side of the highest tide value they want. They are then outputted a dataframe selection
that includes the highest tide and either side data.


"""

# Imported packages
import os
from dotenv import load_dotenv
from datetime import date, datetime, timedelta
import pandas as pd
import requests
from shapely.geometry import Polygon


def get_Tide_data(NIWA_API_KEY: str, lat: float, long: float, total_days: int, startDate: str, datum: str):
    """ returns dataframe that has been concatenated with new data as max output of days data from API is 31"""

    # As the API can only process max 31 days at a time, calculating the remainder and doing 1 API request
    # Then doing 30 * the amount that the days go into 30.
    modulo = total_days % 30
    if modulo == 0:
        numberOfDays = 30
        months = (total_days // 30) - 1
    else:
        numberOfDays = modulo
        months = total_days // 30

    # Setting API parameters
    parameters = {'lat': lat, 'long': long, 'apikey': NIWA_API_KEY, 'numberOfDays': numberOfDays,
                  'startDate': startDate, 'datum': datum}

    # A GET request for NIWA API
    NIWA_API = requests.get('https://api.niwa.co.nz/tides/data', params=parameters)

    # Checking API request is valid and quitting if not
    if NIWA_API.status_code != 200:
        raise ValueError(f"API ERROR: {NIWA_API.status_code} Please check input parameters and try again!")
    else:
        # Fetching values from API request
        Tide_df = pd.DataFrame(NIWA_API.json()['values'])

    # Fetching new data from the API by updating paramaters and using the last start date collected plus a day to form new start date.
    count = 0
    parameters['numberOfDays'] = 30
    while count != months:
        last_val = Tide_df['time'].iloc[-1]
        startDate = str((datetime.strptime(last_val[:10], '%Y-%m-%d') + timedelta(days=1)))[:10]
        parameters['startDate'] = startDate
        print("Start: ", startDate)
        NIWA_API = requests.get('https://api.niwa.co.nz/tides/data', params=parameters)
        new_data = pd.DataFrame(NIWA_API.json()['values'])
        # Concatenating new data to current dataframe
        Tide_df = pd.concat([Tide_df, new_data], ignore_index=True, axis=0)
        count += 1
        print(count, "/", months)

    # rename columns and sort tide values highest to lowest
    Tide_df.rename(columns={'time': 'Datetime_(NZST)', 'value': 'Tide_value_(m)'}, inplace=True)
    Tide_df = Tide_df.sort_values(by=['Tide_value_(m)'], ascending=False)

    # converting time column from a panda series to dataframe object
    Tide_df["Datetime_(NZST)"] = pd.to_datetime(Tide_df["Datetime_(NZST)"], format='%Y-%m-%d %H:%M')

    # Set time as Index
    Tide_df.set_index("Datetime_(NZST)", inplace=True)

    # Convert to NZST
    Tide_df = Tide_df.tz_convert('Pacific/Auckland')

    return Tide_df


def get_highest_tide_data(Tide_df: pd.core.frame.DataFrame, either_side: int):
    """ takes dataframe and finds data either side of peak is required (in days) """
    # setting upper and lowe index
    lower_index = (Tide_df.index[0] - timedelta(days=either_side))
    upper_index = (Tide_df.index[0] + timedelta(days=either_side))
    # Finding highest tide value and return sorted list
    highest_tide = Tide_df.loc[lower_index.strftime('%Y-%m-%d'): upper_index.strftime('%Y-%m-%d')]
    return highest_tide.sort_index().to_string()


def main():
    load_dotenv()
    NIWA_API_KEY = os.getenv("NIWA_API_KEY")

    ## Fetching centroid co-ordinate from user selected shapely polygon
    lat = Polygon([[-43.298137, 172.568351], [-43.279144, 172.833569], [-43.418953, 172.826698],
                   [-43.407542, 172.536636]]).centroid.coords[0][0]
    long = Polygon([[-43.298137, 172.568351], [-43.279144, 172.833569], [-43.418953, 172.826698],
                    [-43.407542, 172.536636]]).centroid.coords[0][1]

    # How many days of tide data to collect (e.g. 365 for 1 years worth):
    total_days = 365
    # Start date (can be in the past or present) for collection of data

    # String for start date of data in format of ('yyyy-mm-dd')
    startDate = date.today()

    # String for datum type.  LAT: Lowest astronomical tide; MSL: Mean sea level
    datum = "LAT"

    # How many days either side of highest tide do you want data for:
    either_side = 1

    Tide_dataframe = get_Tide_data(NIWA_API_KEY, lat, long, total_days, startDate, datum)

    highest_tide_data = get_highest_tide_data(Tide_dataframe, either_side)
    print(highest_tide_data)


if __name__ == "__main__":
    main()
