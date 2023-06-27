# -*- coding: utf-8 -*-
"""
@Description:
@Author: sli229
"""

from datetime import date, timedelta
from math import ceil
from typing import Dict, List, Tuple, Union, Optional
import io
import asyncio

import aiohttp
import geopandas as gpd
import numpy as np
import pandas as pd

from src import config
from src.dynamic_boundary_conditions.tide_enum import DatumType, ApproachType


def get_query_loc_coords_position(query_loc_row: gpd.GeoDataFrame) -> Tuple[float, float, str]:
    query_loc_row = query_loc_row.reset_index(drop=True)
    position = query_loc_row['position'][0]
    query_loc_row = query_loc_row.to_crs(4326)
    query_loc_point = query_loc_row['geometry'][0]
    long, lat = query_loc_point.x, query_loc_point.y
    return lat, long, position


def get_date_ranges(
        start_date: date = date.today(),
        total_days: int = 365,
        days_per_call: int = 31) -> Dict[date, int]:
    """
    Obtain the start date and the duration, measured in days, for each API call made to retrieve tide data
    for the entire requested period.

    Parameters
    ----------
    start_date : date
        The start date for data collection, which can be in the past or present. Default date is today's date.
    total_days: int = 365
        The number of days of tide data to collect. The default value is 365 for one year.
    days_per_call : int = 31
        The number of days that can be retrieved in a single API call (between 1 and 31 inclusive).
        The default value is configured to 31, which is the maximum number of days that can be retrieved per API call.
    """
    # Check for invalid arguments
    if total_days < 1:
        raise ValueError(f"total_days is {total_days}, must be at least 1.")
    # Verify that the provided argument meet the query parameter requirements of the Tide API
    if not 1 <= days_per_call <= 31:
        raise ValueError(f"days_per_call is {days_per_call}, must be between 1 and 31 inclusive.")
    # end date for data retrieval
    end_date = start_date + timedelta(days=total_days - 1)
    # Initialize an empty dictionary to store the date ranges
    date_ranges = {}
    # Loop through the date range, adding each chunk of data to the dictionary
    while start_date <= end_date:
        # Determine the start date and number of days for the current chunk
        request_end_date = min(end_date, start_date + timedelta(days=days_per_call - 1))
        number_of_days = (request_end_date - start_date).days + 1
        # Add the current chunk to the date_ranges dictionary
        date_ranges[start_date] = number_of_days
        # Move the start date forward for the next chunk
        start_date += timedelta(days=number_of_days)
    return date_ranges


def gen_api_query_param_list(
        lat: Union[int, float],
        long: Union[int, float],
        date_ranges: Dict[date, int],
        interval_mins: Optional[int] = None,
        datum: DatumType = DatumType.LAT) -> List[Dict[str, Union[str, int]]]:
    """
    Generate a list of api query parameters used to retrieve high and low tide data for the entire requested period.

    Parameters
    ----------
    lat : Union[int, float]
        Latitude range -29 to -53 (- eg: -30.876).
    long : Union[int, float]
        Longitude range 160 to 180 and -175 to -180 (- eg: -175.543).
    date_ranges : Dict[date, int]
        Dictionary of start date and number of days for each API call that need to be made to retrieve
        high and low tide data for the entire requested period.
    interval_mins: Optional[int] = None
        Output time interval in minutes, range from 10 to 1440 minutes (1 day).
        Omit to get only high and low tide times.
    datum : DatumType = DatumType.LAT
        Datum used. LAT: Lowest astronomical tide; MSL: Mean sea level. Default is LAT.
    """
    # Verify that the provided arguments meet the query parameter requirements of the Tide API
    if not (-53 <= lat <= -29):
        raise ValueError(f"latitude is {lat}, must range from -29 to -53.")
    if not ((160 <= long <= 180) or (-180 <= long <= -175)):
        raise ValueError(f"longitude is {long}, must range from 160 to 180 or from -175 to -180.")
    if interval_mins is not None and not (10 <= interval_mins <= 1440):
        raise ValueError(f"interval is {interval_mins}, must range from 10 to 1440.")
    # Get NIWA api key
    niwa_api_key = config.get_env_variable("NIWA_API_KEY")
    # Create a list of api query parameters for all 'date_ranges'
    query_param_list = []
    for start_date, number_of_days in date_ranges.items():
        query_param = {
            "apikey": niwa_api_key,
            "lat": str(lat),
            "long": str(long),
            "numberOfDays": number_of_days,
            "startDate": start_date.isoformat(),
            "datum": datum.value
        }
        if interval_mins is not None:
            query_param["interval"] = interval_mins
        query_param_list.append(query_param)
    return query_param_list


async def fetch_tide_data(
        session: aiohttp.ClientSession,
        query_param: Dict[str, Union[str, int]],
        url: str = 'https://api.niwa.co.nz/tides/data') -> gpd.GeoDataFrame:
    """
    Fetch high and low tide data for a single query parameter.

    Parameters
    ----------
    session : aiohttp.ClientSession
        An aiohttp ClientSession object.
    query_param : Dict[str, Union[str, int]]
        The query parameters used to retrieve high and low tide data for a specific location and time period.
    url : str, optional
        Tide API HTTP request URL. Defaults to 'https://api.niwa.co.nz/tides/data'.
        Can be either 'https://api.niwa.co.nz/tides/data' or 'https://api.niwa.co.nz/tides/data.csv'.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the fetched high and low tide data.
    """
    async with session.get(url, params=query_param) as resp:
        if url == "https://api.niwa.co.nz/tides/data":
            # Process response as JSON
            resp_dict = await resp.json()
            tide_df = pd.DataFrame(resp_dict['values'])
            tide_df.insert(loc=0, column='datum', value=resp_dict['metadata']['datum'])
            tide_df.insert(loc=1, column='latitude', value=resp_dict['metadata']['latitude'])
            tide_df.insert(loc=2, column='longitude', value=resp_dict['metadata']['longitude'])
        else:
            # Process response as CSV
            resp_text = await resp.text()
            data = pd.read_csv(io.StringIO(resp_text)).reset_index()
            header_index = data[data['index'] == 'TIME'].index[0]
            tide_df = data[header_index + 1:].reset_index(drop=True)
            tide_df.columns = [header.lower() for header in data.iloc[header_index].tolist()]
            tide_df['value'] = tide_df['value'].astype(float)
            tide_df.insert(loc=0, column='datum', value=data[data['index'] == 'Datum'].values[0][1].strip())
            tide_df.insert(loc=1, column='latitude', value=float(data[data['index'] == 'Latitude'].values[0][1]))
            tide_df.insert(loc=2, column='longitude', value=float(data[data['index'] == 'Longitude'].values[0][1]))
        geometry = gpd.points_from_xy(tide_df['longitude'], tide_df['latitude'])
        tide_df = gpd.GeoDataFrame(tide_df, geometry=geometry, crs=4326)
        return tide_df


async def fetch_tide_data_for_requested_period(
        query_param_list: List[Dict[str, Union[str, int]]],
        url: str = 'https://api.niwa.co.nz/tides/data') -> gpd.GeoDataFrame:
    """
    Iterate over the list of API query parameters to fetch high and low tide data for the requested period.

    Parameters
    ----------
    query_param_list : List[Dict[str, Union[str, int]]]
        A list of API query parameters used to retrieve high and low tide data for the entire requested period.
    url : str, optional
        Tide API HTTP request URL. Defaults to 'https://api.niwa.co.nz/tides/data'.
        Can be either 'https://api.niwa.co.nz/tides/data' or 'https://api.niwa.co.nz/tides/data.csv'.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the fetched high and low tide data for the requested period.

    Raises
    ------
    ValueError
        If an invalid URL is specified for the Tide API HTTP request.
    """
    # Validate the URL
    if url not in ["https://api.niwa.co.nz/tides/data", "https://api.niwa.co.nz/tides/data.csv"]:
        raise ValueError(
            "Invalid URL specified for the Tide API HTTP request. "
            "Valid URLs are 'https://api.niwa.co.nz/tides/data' or 'https://api.niwa.co.nz/tides/data.csv'.")

    retry = True
    while retry:
        try:
            tasks = []
            async with aiohttp.ClientSession() as session:
                # Create a list of tasks that fetch tide data for each query parameter
                for query_param in query_param_list:
                    tasks.append(fetch_tide_data(session, query_param=query_param, url=url))
                # Wait for all tasks to complete and concatenate the results into a single DataFrame
                query_results = await asyncio.gather(*tasks, return_exceptions=True)
                tide_data = pd.concat(query_results).reset_index(drop=True)
            retry = False
        except TypeError:
            # If TypeError occurs, switch to the alternative URL and retry
            url = 'https://api.niwa.co.nz/tides/data.csv'
    return tide_data


def convert_to_nz_timezone(tide_data_utc: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Convert the time column in the initially retrieved tide data for the requested period from UTC to NZ timezone.

    Parameters
    ----------
    tide_data_utc : pd.DataFrame
        The original tide data obtained for the requested period with the time column expressed in UTC.
    """
    tide_data = tide_data_utc.copy()
    tide_data['time'] = pd.to_datetime(tide_data['time'])
    tide_data['time'] = tide_data['time'].dt.tz_convert(tz='Pacific/Auckland')
    return tide_data


def fetch_tide_data_from_niwa(
        tide_query_loc: gpd.GeoDataFrame,
        datum: DatumType = DatumType.LAT,
        start_date: date = date.today(),
        total_days: int = 365,
        interval_mins: Optional[int] = None) -> gpd.GeoDataFrame:
    """
    Retrieve tide data from NIWA for the requested time period using the centroid coordinates of the catchment area.

    Parameters
    ----------
    tide_query_loc : gpd.GeoDataFrame
        GeoPandas dataframe containing the query coordinate and its position.
    datum : DatumType = DatumType.LAT
        Datum used. LAT: Lowest astronomical tide; MSL: Mean sea level. Default is LAT.
    start_date : date
        The start date for data collection, which can be in the past or present. Default date is today's date.
    total_days: int = 365
        The number of days of tide data to collect. The default value is 365 for one year.
    interval_mins: Optional[int] = None
        Output time interval in minutes, range from 10 to 1440 minutes (1 day).
        Omit to get only high and low tide times.
    """
    # Get the date_ranges (i.e. start date and the duration used for each API call)
    date_ranges = get_date_ranges(start_date, total_days)
    # Get the tide data for each of the tide query location
    tide_data_utc = pd.DataFrame()
    for _, row in tide_query_loc.iterrows():
        query_loc_row = gpd.GeoDataFrame([row], crs=tide_query_loc.crs)
        lat, long, position = get_query_loc_coords_position(query_loc_row)
        # Get the list of api query parameters used to retrieve high and low tide data
        query_param_list = gen_api_query_param_list(lat, long, date_ranges, interval_mins, datum)
        # Iterate over the list of API query parameters to fetch high and low tide data for the requested period
        query_loc_tide = asyncio.run(fetch_tide_data_for_requested_period(query_param_list))
        query_loc_tide['position'] = position
        tide_data_utc = pd.concat([tide_data_utc, query_loc_tide])
    # Convert time column from UTC to NZ timezone.
    tide_data = convert_to_nz_timezone(tide_data_utc)
    # Filter out data and reset index
    end_date = start_date + timedelta(days=total_days - 1)
    tide_data = tide_data.loc[tide_data['time'].dt.date <= end_date]
    tide_data = tide_data.reset_index(drop=True)
    # Rename columns
    new_col_names = {'time': 'datetime_nz', 'value': 'tide_metres'}
    tide_data.rename(columns=new_col_names, inplace=True)
    return tide_data


def get_highest_tide_datetime(tide_data: gpd.GeoDataFrame) -> pd.Timestamp:
    """
    Get the datetime of the most recent highest tide that occurred within the requested time period.

    Parameters
    ----------
    tide_data : gpd.GeoDataFrame
        The original tide data obtained for the requested period with the time column expressed in NZ timezone
        (converted from UTC).
    """
    # Find the highest tide value
    max_tide_value = tide_data['tide_metres'].max()
    highest_tide = tide_data[tide_data['tide_metres'] == max_tide_value]
    # Get the datetime of the most recent highest tide
    highest_tide = highest_tide.sort_values(by=['datetime_nz'], ascending=False).reset_index(drop=True)
    highest_tide_datetime = highest_tide.iloc[0]['datetime_nz']
    return highest_tide_datetime


def get_highest_tide_datetime_span(
        highest_tide_datetime: pd.Timestamp,
        tide_length_mins: int) -> Tuple[pd.Timestamp, pd.Timestamp]:
    half_tide_length_mins = tide_length_mins / 2
    half_tide_length_timedelta = timedelta(minutes=half_tide_length_mins)
    start_datetime = highest_tide_datetime - half_tide_length_timedelta
    end_datetime = highest_tide_datetime + half_tide_length_timedelta
    end_datetime -= timedelta(seconds=1)
    return start_datetime, end_datetime


def get_highest_tide_date_span(start_datetime: pd.Timestamp, end_datetime: pd.Timestamp) -> Tuple[date, int]:
    start_date = start_datetime.date()
    end_date = end_datetime.date()
    total_days = (end_date - start_date).days + 1
    return start_date, total_days


def get_time_mins_to_add(
        tide_data: gpd.GeoDataFrame,
        tide_length_mins: int,
        time_to_peak_mins: int,
        interval_mins: int = 10) -> np.ndarray:
    row_count = len(tide_data)
    time_mins = np.arange(1, row_count + 1) * interval_mins
    if time_mins[-1] > tide_length_mins:
        time_mins = np.insert(time_mins[:-1], 0, 0)
    middle_index = ceil(len(time_mins) / 2) - 1
    middle_point = time_mins[middle_index]
    adjustment = time_to_peak_mins - middle_point
    time_mins = time_mins + adjustment
    return time_mins


def add_time_information(
        tide_data: gpd.GeoDataFrame,
        time_to_peak_mins: int,
        total_days: Optional[int] = None,
        tide_length_mins: Optional[int] = None,
        interval_mins: int = 10,
        approach: ApproachType = ApproachType.KING_TIDE) -> gpd.GeoDataFrame:
    if approach == ApproachType.PERIOD_TIDE and total_days is not None:
        tide_length_mins = total_days * 24 * 60

    min_time_to_peak_mins = tide_length_mins / 2
    if time_to_peak_mins < min_time_to_peak_mins:
        raise ValueError("'time_to_peak_mins' needs to be at least half of the duration of the tide in minutes.")

    time_mins = get_time_mins_to_add(tide_data, tide_length_mins, time_to_peak_mins, interval_mins)
    grouped = tide_data.groupby(['position', tide_data['geometry'].to_wkt()])
    tide_data_w_time = gpd.GeoDataFrame()
    for _, group_data in grouped:
        group_data = group_data.sort_values(by='datetime_nz')
        group_data['mins'] = time_mins.tolist()
        group_data['hours'] = group_data['mins'] / 60
        group_data['seconds'] = group_data['mins'] * 60
        group_data = group_data.sort_values(by="seconds").reset_index(drop=True)
        tide_data_w_time = pd.concat([tide_data_w_time, group_data])
    tide_data_w_time = tide_data_w_time.reset_index(drop=True)
    return tide_data_w_time


def fetch_highest_tide_side_data_from_niwa(
        tide_data: gpd.GeoDataFrame,
        tide_length_mins: int,
        interval_mins: int,
        datum: DatumType = DatumType.LAT) -> gpd.GeoDataFrame:
    grouped = tide_data.groupby(['position', tide_data['geometry'].to_wkt()])
    data_around_highest_tide = gpd.GeoDataFrame()
    for _, group_data in grouped:
        # noinspection PyTypeChecker
        highest_tide_datetime = get_highest_tide_datetime(group_data)
        start_datetime, end_datetime = get_highest_tide_datetime_span(highest_tide_datetime, tide_length_mins)
        start_date, total_days = get_highest_tide_date_span(start_datetime, end_datetime)
        # get unique pairs of coordinates
        highest_tide_query_loc = group_data[['position', 'geometry']].drop_duplicates().reset_index(drop=True)
        highest_tide_data = fetch_tide_data_from_niwa(
            highest_tide_query_loc, datum, start_date, total_days, interval_mins)
        highest_tide_data = highest_tide_data.loc[
            highest_tide_data['datetime_nz'].between(start_datetime, end_datetime)].reset_index(drop=True)
        data_around_highest_tide = pd.concat([data_around_highest_tide, highest_tide_data])
    data_around_highest_tide = data_around_highest_tide.reset_index(drop=True)
    return data_around_highest_tide


def get_tide_data(
        tide_query_loc: gpd.GeoDataFrame,
        time_to_peak_mins: int,
        approach: ApproachType = ApproachType.KING_TIDE,
        start_date: date = date.today(),
        total_days: Optional[int] = None,
        tide_length_mins: Optional[int] = None,
        interval_mins: int = 10,
        datum: DatumType = DatumType.LAT) -> gpd.GeoDataFrame:
    if approach == ApproachType.KING_TIDE:
        if total_days is not None:
            raise ValueError("total_days parameter should not be provided for ApproachType.KING_TIDE")
        if tide_length_mins is None:
            raise ValueError("tide_length_mins parameter must be provided for ApproachType.KING_TIDE")
        if interval_mins is None:
            raise ValueError("interval_mins parameter must be provided for ApproachType.KING_TIDE")
        tide_data = fetch_tide_data_from_niwa(
            tide_query_loc, datum, start_date, total_days=365, interval_mins=None)
        data_around_highest_tide = fetch_highest_tide_side_data_from_niwa(
            tide_data, tide_length_mins, interval_mins, datum)
        tide_data_king = add_time_information(
            tide_data=data_around_highest_tide,
            tide_length_mins=tide_length_mins,
            time_to_peak_mins=time_to_peak_mins,
            interval_mins=interval_mins,
            approach=approach)
        return tide_data_king
    else:
        if tide_length_mins is not None:
            raise ValueError("tide_length_mins parameter should not be provided for ApproachType.PERIOD_TIDE")
        if total_days is None:
            raise ValueError("total_days parameter must be provided for ApproachType.PERIOD_TIDE")
        if interval_mins is None:
            raise ValueError("interval_mins parameter must be provided for ApproachType.PERIOD_TIDE")
        tide_data = fetch_tide_data_from_niwa(tide_query_loc, datum, start_date, total_days, interval_mins)
        tide_data_period = add_time_information(
            tide_data=tide_data,
            total_days=total_days,
            time_to_peak_mins=time_to_peak_mins,
            interval_mins=interval_mins,
            approach=approach)
        return tide_data_period
