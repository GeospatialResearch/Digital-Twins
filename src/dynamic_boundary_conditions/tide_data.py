# -*- coding: utf-8 -*-
"""
Created on Tue Oct 18 16:30:21 2022.

@author: alo78
"""

import os
from dotenv import load_dotenv
from datetime import date, datetime, timedelta
import pandas as pd
import requests



def get_Tide_data(NIWA_API_KEY, lat, long, total_days, startDate, datum):
    """ returns dataframe that has been concatenated with new data as max output of days data from API is 31"""
    modulo = total_days % 30
    if modulo == 0:
        numberOfDays = 30
        months = (total_days // 30) - 1
    else:
        numberOfDays = modulo
        months = total_days // 30

    parameters = {'lat': lat, 'long': long, 'apikey': NIWA_API_KEY, 'numberOfDays': numberOfDays,
                  'startDate': startDate, 'datum': datum}

    # A GET request for NIWA API
    NIWA_API = requests.get('https://api.niwa.co.nz/tides/data', params=parameters)

    if NIWA_API.status_code != 200:
        print("API ERROR: ", NIWA_API.status_code)
        print("Please check input and try again!")
        quit()
    else:
        Tide_df = pd.DataFrame(NIWA_API.json()['values'][2:])
        api_check = False

    count = 0
    parameters['numberOfDays'] = 30
    while count != months:
        last_val = Tide_df['time'].iloc[-1]
        startDate = str((datetime.strptime(last_val[:10], '%Y-%m-%d') + timedelta(days=1)))[:10]
        parameters['startDate'] = startDate
        print("Start: ", startDate)

        NIWA_API = requests.get('https://api.niwa.co.nz/tides/data', params=parameters)
        # print(NIWA_API.json()['values'])
        new_data = pd.DataFrame(NIWA_API.json()['values'])
        Tide_df = pd.concat([Tide_df, new_data], ignore_index=True, axis=0)
        count += 1
        print(count, "/", months)

    # sort tide values highest to lowest
    Tide_df.rename(columns={'time': 'Datetime_(NZST)', 'value': 'Tide_value_(m)'}, inplace=True)
    Tide_df = Tide_df.sort_values(by=['Tide_value_(m)'], ascending=False)

    # converting time column from a panda series to dataframe object
    Tide_df["Datetime_(NZST)"] = pd.to_datetime(Tide_df["Datetime_(NZST)"], format='%Y-%m-%d %H:%M')

    # Set time as Index
    Tide_df.set_index("Datetime_(NZST)", inplace=True)

    # Convert to NZST
    Tide_df = Tide_df.tz_convert('Pacific/Auckland')

    return Tide_df



def get_highest_tide_data(Tide_df, either_side):
    """ takes dataframe and finds data either side of peak is required (in days) """
    lower_index = (Tide_df.index[0] - timedelta(days=either_side))
    upper_index = (Tide_df.index[0] + timedelta(days=either_side))
    highest_tide = Tide_df.loc[lower_index.strftime('%Y-%m-%d'): upper_index.strftime('%Y-%m-%d')]
    return highest_tide.sort_index().to_string()








def main():


    load_dotenv()
    NIWA_API_KEY = os.getenv("NIWA_API_KEY")
    lat = -30.876
    long = -175.543
    total_days = 365
    startDate = date.today()
    datum = "LAT"

    either_side = 1




    Tide_df = get_Tide_data(NIWA_API_KEY, lat, long, total_days, startDate, datum)

    highest_tide_data = get_highest_tide_data(Tide_df, either_side)
    print(highest_tide_data)




if __name__ == "__main__":
    main()