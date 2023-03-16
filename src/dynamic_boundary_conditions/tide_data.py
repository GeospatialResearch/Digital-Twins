import logging
import pathlib
from datetime import date, timedelta
from typing import Dict, List, Tuple, Union, Optional

import pandas as pd
import geopandas as gpd
import asyncio
import aiohttp

from src import config
from src.dynamic_boundary_conditions.tide_enum import DatumType

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def get_catchment_centroid_coords(catchment_file: pathlib.Path) -> Tuple[float, float]:
    """
    Extract the catchment polygon centroid coordinates.

    Parameters
    ----------
    catchment_file : pathlib.Path
        The file path for the catchment polygon.
    """
    catchment = gpd.read_file(catchment_file)
    catchment = catchment.to_crs(4326)
    catchment_polygon = catchment["geometry"][0]
    long, lat = catchment_polygon.centroid.coords[0]
    return lat, long


def get_date_ranges(
        start_date: date,
        total_days: int = 365,
        days_per_call: int = 31) -> Dict[date, int]:
    """
    Obtain the start date and the duration, measured in days, for each API call made to retrieve tide data
    for the entire requested period.

    Parameters
    ----------
    start_date : date
        The start date for data collection, which can be in the past or present.
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
        api_key: str,
        lat: Union[int, float],
        long: Union[int, float],
        datum: DatumType,
        date_ranges: Dict[date, int],
        interval: Optional[int] = None) -> List[Dict[str, Union[str, int]]]:
    """
    Generate a list of api query parameters used to retrieve high and low tide data for the entire requested period.

    Parameters
    ----------
    api_key : str
        NIWA api key (https://developer.niwa.co.nz/).
    lat : Union[int, float]
        Latitude range -29 to -53 (- eg: -30.876).
    long : Union[int, float]
        Longitude range 160 to 180 and -175 to -180 (- eg: -175.543).
    datum : DatumType
        Datum used. LAT: Lowest astronomical tide; MSL: Mean sea level.
    date_ranges : Dict[date, int]
        Dictionary of start date and number of days for each API call that need to be made to retrieve
        high and low tide data for the entire requested period.
    interval: Optional[int] = None
        Output time interval in minutes, range from 10 to 1440 minutes (1 day).
        Omit to get only high and low tide times.
    """
    # Verify that the provided arguments meet the query parameter requirements of the Tide API
    if not (-53 <= lat <= -29):
        raise ValueError(f"latitude is {lat}, must range from -29 to -53.")
    if not ((160 <= long <= 180) or (-180 <= long <= -175)):
        raise ValueError(f"longitude is {long}, must range from 160 to 180 or from -175 to -180.")
    if interval is not None and not (10 <= interval <= 1440):
        raise ValueError(f"interval is {interval}, must range from 10 to 1440.")
    # Create a list of api query parameters for all 'date_ranges'
    query_param_list = []
    for start_date, number_of_days in date_ranges.items():
        query_param = {
            "apikey": api_key,
            "lat": str(lat),
            "long": str(long),
            "numberOfDays": number_of_days,
            "startDate": start_date.isoformat(),
            "datum": datum.value
        }
        if interval is not None:
            query_param["interval"] = interval
        query_param_list.append(query_param)
    return query_param_list


async def fetch_tide_data(
        session: aiohttp.ClientSession,
        query_param: Dict[str, Union[str, int]],
        url: str = 'https://api.niwa.co.nz/tides/data'):
    """
    Fetch high and low tide data for a single query parameter.

    Parameters
    ----------
    session : aiohttp.ClientSession
        An aiohttp ClientSession object.
    query_param : Dict[str, Union[str, int]]
        The query parameters used to retrieve high and low tide data for a specific location and time period.
    url: str = 'https://api.niwa.co.nz/tides/data'
        Tide API HTTP request url.
    """
    async with session.get(url, params=query_param) as resp:
        resp_dict = await resp.json()
        tide_df = pd.DataFrame(resp_dict['values'])
        tide_df.insert(loc=0, column='datum', value=query_param['datum'])
        tide_df.insert(loc=1, column='latitude', value=query_param['lat'])
        tide_df.insert(loc=2, column='longitude', value=query_param['long'])
        return tide_df


async def get_tide_data_for_requested_period(
        query_param_list: List[Dict[str, Union[str, int]]],
        url: str = 'https://api.niwa.co.nz/tides/data'):
    """
    Iterate over the list of API query parameters to fetch high and low tide data for the requested period.

    Parameters
    ----------
    query_param_list : List[Dict[str, Union[str, int]]]
        A list of api query parameters used to retrieve high and low tide data for the entire requested period.
    url: str = 'https://api.niwa.co.nz/tides/data'
        Tide API HTTP request url.
    """
    tasks = []
    async with aiohttp.ClientSession() as session:
        # Create a list of tasks that fetch tide data for each query parameter
        for query_param in query_param_list:
            tasks.append(fetch_tide_data(session, query_param=query_param, url=url))
        # Wait for all tasks to complete and concatenate the results into a single DataFrame
        query_results = await asyncio.gather(*tasks, return_exceptions=True)
        tide_data = pd.concat(query_results)
    return tide_data


def convert_to_nz_timezone(tide_data: pd.DataFrame) -> pd.DataFrame:
    """
    Convert the time column in the initially retrieved tide data for the requested period from UTC to NZ timezone.

    Parameters
    ----------
    tide_data : pd.DataFrame
        The original tide data obtained for the requested period with the time column expressed in UTC.
    """
    tide_data['time'] = pd.to_datetime(tide_data['time'])
    tide_data['time'] = tide_data['time'].dt.tz_convert(tz='Pacific/Auckland')
    return tide_data


def get_tide_data_from_niwa(
        catchment_file: pathlib.Path,
        api_key: str,
        datum: DatumType,
        start_date: date,
        total_days: int = 365,
        interval: Optional[int] = None) -> pd.DataFrame:
    """
    Retrieve tide data from NIWA for the requested time period using the centroid coordinates of the catchment area.

    Parameters
    ----------
    catchment_file : pathlib.Path
        The file path for the catchment polygon.
    api_key : str
        NIWA api key (https://developer.niwa.co.nz/).
    datum : DatumType
        Datum used. LAT: Lowest astronomical tide; MSL: Mean sea level.
    start_date : date
        The start date for data collection, which can be in the past or present.
    total_days: int = 365
        The number of days of tide data to collect. The default value is 365 for one year.
    interval: Optional[int] = None
        Output time interval in minutes, range from 10 to 1440 minutes (1 day).
        Omit to get only high and low tide times.
    """
    # Get the catchment polygon centroid coordinates.
    lat, long = get_catchment_centroid_coords(catchment_file)
    # Get the date_ranges (i.e. start date and the duration used for each API call)
    date_ranges = get_date_ranges(start_date, total_days)
    # Get the list of api query parameters used to retrieve high and low tide data
    query_param_list = gen_api_query_param_list(api_key, lat, long, datum, date_ranges, interval)
    # Iterate over the list of API query parameters to fetch high and low tide data for the requested period
    tide_data_utc = asyncio.run(get_tide_data_for_requested_period(query_param_list))
    # Convert time column from UTC to NZ timezone.
    tide_data = convert_to_nz_timezone(tide_data_utc)
    # Rename columns
    new_col_names = {'time': 'datetime_nz', 'value': 'tide_metres'}
    tide_data.rename(columns=new_col_names, inplace=True)
    return tide_data


def get_highest_tide_datetime(tide_data: pd.DataFrame) -> pd.Timestamp:
    """
    Get the datetime of the most recent highest tide that occurred within the requested time period.

    Parameters
    ----------
    tide_data : pd.DataFrame
        The original tide data obtained for the requested period with the time column expressed in NZ timezone
        (converted from UTC).
    """
    # Find the highest tide value
    max_tide_value = tide_data['tide_metres'].max()
    highest_tide = tide_data[tide_data['tide_metres'] == max_tide_value]
    # Get the datetime of the most recent highest tide
    highest_tide = highest_tide.sort_values(by=['datetime_nz'], ascending=False).reset_index(drop=True)
    highest_tide_datetime = highest_tide.iloc[0]['datetime_nz']
    log.info(f"The highest tide datetime is: {highest_tide_datetime}")
    return highest_tide_datetime


def get_highest_tide_side_dates(
        tide_data: pd.DataFrame,
        days_before_peak: int,
        days_after_peak: int) -> List[date]:
    """
    Get a list of dates for the requested time period surrounding the highest tide. This includes all dates from
    the start date (the first day before the highest tide) to the end date (the last day after the highest tide).

    Parameters
    ----------
    tide_data : pd.DataFrame
        The original tide data obtained for the requested period with the time column expressed in NZ timezone
        (converted from UTC).
    days_before_peak : int
        An integer representing the number of days before the highest tide to extract data for.
        Must be a positive integer.
    days_after_peak : int
        An integer representing the number of days after the highest tide to extract data for.
        Must be a positive integer.
    """
    # Check for invalid arguments
    if days_before_peak < 0:
        raise ValueError("'days_before_peak' must be at least 0.")
    if days_after_peak < 0:
        raise ValueError("'days_after_peak' must be at least 0.")
    #  Get the datetime of the most recent highest tide that occurred within the requested time period.
    highest_tide_datetime = get_highest_tide_datetime(tide_data)
    # Get the start_date (first day before peak) and the end_date (last day after peak)
    start_date = highest_tide_datetime.date() - timedelta(days=days_before_peak)
    end_date = highest_tide_datetime.date() + timedelta(days=days_after_peak)
    # Get a list of dates from start_date (first day before peak) to end_date (last day after peak)
    dates_list = pd.date_range(start_date, end_date, freq='D').date.tolist()
    return dates_list


def find_existing_and_missing_dates(
        tide_data: pd.DataFrame,
        dates_list: List[date]) -> Tuple[List[date], List[date]]:
    """
    Check whether each date in the given list of dates is present or missing in the 'datetime_nz' column of the
    given tide_data DataFrame. Returns two lists - existing_dates and missing_dates.
    'existing_dates' contains dates from 'dates_list' that are present in the 'tide_data' DataFrame and
    'missing_dates' contains dates from 'dates_list' that are not present in the 'tide_data' DataFrame.
    The tide data for the missing dates needs to be fetched from NIWA to obtain a complete set of required
    tide data surrounding the highest tide.

    Parameters
    ----------
    tide_data : pd.DataFrame
        The original tide data obtained for the requested period with the time column expressed in NZ timezone
        (converted from UTC).
    dates_list: List[date]
        A list of dates for the requested time period surrounding the highest tide. This includes all dates from
        the start date (the first day before the highest tide) to the end date (the last day after the highest tide).
    """
    tide_data_dates = set(tide_data['datetime_nz'].dt.date)
    dates_set = set(dates_list)
    existing_dates = sorted(list(tide_data_dates.intersection(dates_set)))
    missing_dates = sorted(list(dates_set - tide_data_dates))
    return existing_dates, missing_dates


def get_missing_dates_date_ranges(missing_dates: List[date]) -> Dict[date, int]:
    """
    Returns a dictionary containing the start date and the duration, measured in days, required to retrieve
    tide data from NIWA for a given list of missing dates.

    Parameters
    ----------
    missing_dates : List[date]
        A list of missing dates to group.
    """
    missing_dates_date_ranges = {}
    start_date = missing_dates[0]
    for i in range(1, len(missing_dates)):
        if (missing_dates[i] - missing_dates[i - 1]).days > 1:
            missing_dates_date_ranges[start_date] = (missing_dates[i - 1] - start_date).days + 1
            start_date = missing_dates[i]
    missing_dates_date_ranges[start_date] = (missing_dates[-1] - start_date).days + 1
    return missing_dates_date_ranges


def get_missing_tide_data_from_niwa(
        catchment_file: pathlib.Path,
        api_key: str,
        datum: DatumType,
        missing_dates: List[date],
        interval: Optional[int] = None) -> pd.DataFrame:
    """
    Retrieve tide data from NIWA for the dates that were not included in the originally obtained tide data.

    Parameters
    ----------
    catchment_file : pathlib.Path
        The file path for the catchment polygon.
    api_key : str
        NIWA api key (https://developer.niwa.co.nz/).
    datum : DatumType
        Datum used. LAT: Lowest astronomical tide; MSL: Mean sea level.
    missing_dates : List[date]
        A collection of dates that are absent from the originally retrieved tide data.
    interval: Optional[int] = None
        Output time interval in minutes, range from 10 to 1440 minutes (1 day).
        Omit to get only high and low tide times.
    """
    missing_tide_data = pd.DataFrame()
    if missing_dates:
        missing_dates_date_ranges = get_missing_dates_date_ranges(missing_dates)
        for start_date, number_of_days in missing_dates_date_ranges.items():
            missing_dt_data = get_tide_data_from_niwa(
                catchment_file=catchment_file,
                api_key=api_key,
                datum=datum,
                start_date=start_date,
                total_days=number_of_days,
                interval=interval)
            missing_tide_data = pd.concat([missing_tide_data, missing_dt_data])
    return missing_tide_data


def get_highest_tide_side_data(
        catchment_file: pathlib.Path,
        api_key: str,
        datum: DatumType,
        tide_data: pd.DataFrame,
        days_before_peak: int,
        days_after_peak: int,
        interval: Optional[int] = None):
    """
    Get the requested tide data for both sides of the highest tide, including the data for the highest tide itself.

    Parameters
    ----------
    catchment_file : pathlib.Path
        The file path for the catchment polygon.
    api_key : str
        NIWA api key (https://developer.niwa.co.nz/).
    datum : DatumType
        Datum used. LAT: Lowest astronomical tide; MSL: Mean sea level.
    tide_data : pd.DataFrame
        The original tide data obtained for the requested period with the time column expressed in NZ timezone
        (converted from UTC).
    days_before_peak : int
        An integer representing the number of days before the highest tide to extract data for.
        Must be a positive integer.
    days_after_peak : int
        An integer representing the number of days after the highest tide to extract data for.
        Must be a positive integer.
    interval: Optional[int] = None
        Output time interval in minutes, range from 10 to 1440 minutes (1 day).
        Omit to get only high and low tide times.
    """
    # Get a list of dates from start_date (first day before peak) to end_date (last day after peak)
    dates_list = get_highest_tide_side_dates(tide_data, days_before_peak, days_after_peak)
    # Get the missing dates that are not present in the original tide data
    existing_dates, missing_dates = find_existing_and_missing_dates(tide_data, dates_list)
    # Get the tide data for the existing dates from the original tide data
    existing_tide_data = tide_data[tide_data['datetime_nz'].dt.date.isin(existing_dates)]
    # Retrieve tide data from NIWA for the missing dates
    missing_tide_data = get_missing_tide_data_from_niwa(catchment_file, api_key, datum, missing_dates, interval)
    # Concatenate the tide data for both existing and missing dates
    data_surrounding_highest_tide = pd.concat([existing_tide_data, missing_tide_data])
    # Sort the data by the 'datetime_nz' column in ascending order and reset the index to start from 0
    data_surrounding_highest_tide = data_surrounding_highest_tide.sort_values(by=['datetime_nz']).reset_index(drop=True)
    return data_surrounding_highest_tide


def main():
    # Catchment polygon
    catchment_file = pathlib.Path(r"selected_polygon.geojson")
    # Get NIWA api key
    niwa_api_key = config.get_env_variable("NIWA_API_KEY")
    # Specify the datum query parameter
    datum = DatumType.LAT
    # Get tide data
    tide_data = get_tide_data_from_niwa(
        catchment_file=catchment_file,
        api_key=niwa_api_key,
        datum=datum,
        start_date=date(2023, 1, 24),
        total_days=3,
        interval=None)
    print(tide_data)
    data_surrounding_highest_tide = get_highest_tide_side_data(
        catchment_file=catchment_file,
        api_key=niwa_api_key,
        datum=datum,
        tide_data=tide_data,
        days_before_peak=5,
        days_after_peak=5,
        interval=None)
    print(data_surrounding_highest_tide)


if __name__ == "__main__":
    main()
