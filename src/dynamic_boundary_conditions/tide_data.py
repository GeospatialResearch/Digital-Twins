# -*- coding: utf-8 -*-
"""
Created on Tue Oct 18 16:30:21 2022.

@author: alo78,
         xander.cai@pg.canterbury.ac.nz

Used to get the tide model predictions for site closest to the chosen latitude & longitude (Anywhere on the NZ
Coastline) point from the API created by NIWA (https://developer.niwa.co.nz/docs/tide-api/1/overview). User can
specify how many days of data is required and how much data (in days) either side of the highest tide value they
want. They are then outputted a dataframe selection
that includes the highest tide and either side data.
"""

# Imported packages
from dotenv import load_dotenv
from datetime import date, datetime, timedelta
import pandas as pd
from shapely.geometry import Polygon
import aiohttp
import asyncio
from src.digitaltwin import setup_environment


def get_all_date(start_date: str, total_days: int, max_range: int = 30) -> dict:
    """ get each start date and number of days for total days. """
    start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    start_date_dict = {start_date: 0}
    while total_days > 0:
        if total_days > max_range:
            start_date_dict[(sorted(start_date_dict.keys()))[-1]] = 30
            start_date_dict[(sorted(start_date_dict.keys())[-1] + timedelta(days=max_range))] = total_days - 31
        else:
            start_date_dict[(sorted(start_date_dict.keys()))[-1]] = total_days
        total_days -= 30
    return start_date_dict


def gen_param_list(start_date_dict: dict, request_parameters: dict) -> list:
    """ generate a parameters list for all request. """
    params_list = []
    for start_date, number_of_days in start_date_dict.items():
        params = request_parameters.copy()
        params['startDate'] = start_date.isoformat()
        params['numberOfDays'] = number_of_days
        params_list.append(params)
    return params_list


async def get(session: aiohttp.ClientSession, url: str, params: dict) -> dict:
    """ request get data from url """
    resp = await session.request('GET', url=url, params=params)
    return await resp.json()


async def get_tide_dataframe(params_list: list, url: str = 'https://api.niwa.co.nz/tides/data') -> pd.DataFrame:
    """ Asynchronous context manager. """
    async with aiohttp.ClientSession() as session:
        tasks = []
        for params in params_list:
            tasks.append(get(session=session, url=url, params=params))
        # asyncio.gather() will wait on the entire task set to be completed.
        data_dict = await asyncio.gather(*tasks, return_exceptions=True)
        data_list = [_dict['values'] for _dict in data_dict]
        df = pd.DataFrame([_item for _list in data_list for _item in _list])
        return df


def get_highest_tide_dataframe(df: pd.DataFrame, before_n_days: int, after_n_days: int) -> pd.DataFrame:
    """ takes dataframe and finds data either side of peak is required (in days) """
    # sort dataframe by tide value.
    df['time'] = pd.to_datetime(df['time'])
    df['time'] = df['time'].dt.tz_convert(tz='Pacific/Auckland')
    df = df.sort_values(by=['value'], ascending=False).reset_index(drop=True)
    df.set_index('time', inplace=True)
    print("Highest tide date is: {}".format(df.index[0]))
    # setting upper and lower index, index 0 is the highest tide date
    lower_boundary = (df.index[0] - timedelta(days=max(before_n_days, 0)))
    upper_boundary = (df.index[0] + timedelta(days=max(after_n_days, 0)))
    # protect index boundary.
    assert lower_boundary.strftime('%Y-%m-%d') in df.index, \
        f"Index overflow: lower boundary {lower_boundary} is not in dataframe index."
    assert upper_boundary.strftime('%Y-%m-%d') in df.index, \
        f"Index overflow: upper boundary {upper_boundary} is not in dataframe index."
    # get dataframe between lower and upper boundary date.
    df = (df.sort_values(by=['time'])
            .loc[lower_boundary.strftime('%Y-%m-%d'):upper_boundary.strftime('%Y-%m-%d')])
    # convert dataframe schema for sql
    df.reset_index(inplace=True)
    df['time'] = df['time'].astype(str)
    df.columns = ['Datetime_(NZST)', 'Tide_value_(m)']
    return df


def save_to_database(connect, df: pd.DataFrame, table_name: str, if_exists: str = 'replace'):
    """ save dataframe to database """
    df.to_sql(table_name, connect, index=False, if_exists=if_exists)


def main():

    load_dotenv()

    engine = setup_environment.get_database()

    api_key = os.getenv("NIWA_API_KEY")

    # Fetching centroid co-ordinate from user selected shapely polygon
    latitude = Polygon([[-43.298137, 172.568351],
                        [-43.279144, 172.833569],
                        [-43.418953, 172.826698],
                        [-43.407542, 172.536636]
                        ]).centroid.coords[0][0]

    longitude = Polygon([[-43.298137, 172.568351],
                         [-43.279144, 172.833569],
                         [-43.418953, 172.826698],
                         [-43.407542, 172.536636]
                         ]).centroid.coords[0][1]

    # How many days of tide data to collect (e.g. 365 for 1 years worth):
    total_days = 365

    # Start date (can be in the past or present) for collection of data
    # String for start date of data in format of ('yyyy-mm-dd')
    start_date = date.today().isoformat()

    # String for datum type.  LAT: Lowest astronomical tide; MSL: Mean sea level
    datum = "LAT"

    # How many days either side of the highest tide do you want data for:
    before_n_days = 2
    after_n_days = 4

    request_parameters = {
        'apikey': api_key,
        'lat': latitude,  # string, latitude range -29 to -53 (- eg: -30.876)
        'long': longitude,  # string, longitude range 160 to 180 and -175 to -180 (- eg: -175.543)
        'numberOfDays': total_days,  # number, number of days, range(1 - 31), default: 7
        'startDate': start_date,  # string, start date, format ('yyyy-mm-dd'), default: today (-eg: 2018-05-30)
        'datum': datum  # string, LAT: Lowest astronomical tide; MSL: Mean sea level, default: LAT
    }

    # start process
    start_date_dict = get_all_date(request_parameters['startDate'], request_parameters['numberOfDays'])
    request_parameters_list = gen_param_list(start_date_dict, request_parameters)
    tide_dataframe = asyncio.run(get_tide_dataframe(request_parameters_list))
    highest_tide_df = get_highest_tide_dataframe(tide_dataframe, before_n_days, after_n_days)
    save_to_database(engine, highest_tide_df, 'highest_tide')
    # end process

    print(highest_tide_df)


if __name__ == "__main__":
    main()
