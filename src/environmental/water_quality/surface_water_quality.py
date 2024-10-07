# -*- coding: utf-8 -*-
"""
Fetch and clean surface water quality data from ECAN, store it in the database, and
retrieve it for the requested area of interest.
"""  # noqa: D400

import asyncio
import logging
from http import HTTPStatus
from io import StringIO
from typing import List, Optional

import aiohttp
import geopandas as gpd
import pandas as pd
from sqlalchemy.engine import Engine
from sqlalchemy.sql import text

from src.digitaltwin.tables import check_table_exists
from src.environmental.water_quality.surface_water_sites import get_surface_water_sites_from_db

log = logging.getLogger(__name__)


class NoSurfaceWaterSitesException(Exception):
    """Exception raised when no surface water sites are found within the requested catchment area."""


class NoSurfaceWaterQualityException(Exception):
    """
    Exception raised when the `surface_water_quality` table is missing or
    when no surface water quality data is found for the requested catchment area.
    """  # noqa: D400


def clean_raw_surface_water_quality(surface_water_quality: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and process the raw surface water quality data retrieved from ECAN.

    Parameters
    ----------
    surface_water_quality : pd.DataFrame
        A DataFrame containing the raw surface water quality data retrieved from ECAN.

    Returns
    -------
    pd.DataFrame
        A DataFrame containing the cleaned and processed surface water quality data.
    """
    # Convert all column names to lowercase and replace spaces with underscores to ensure consistency
    surface_water_quality.columns = surface_water_quality.columns.str.lower().str.replace(' ', '_')
    # Convert specified columns to string type and strip any leading and trailing whitespace
    surface_water_quality['site_id'] = surface_water_quality['site_id'].astype(str).str.strip()
    surface_water_quality['sampleid'] = surface_water_quality['sampleid'].astype(str).str.strip()
    surface_water_quality['value'] = surface_water_quality['value'].astype(str).str.strip()
    surface_water_quality['units'] = surface_water_quality['units'].astype(str).str.strip()
    surface_water_quality['measurement'] = surface_water_quality['measurement'].astype(str).str.strip()
    # Convert the 'collection_date' column to datetime format using the specified format
    surface_water_quality["collection_date"] = pd.to_datetime(
        surface_water_quality["collection_date"],
        format="%d-%b %Y %H:%M%p"
    )
    # Remove unnecessary trailing zeros from the 'value' column
    surface_water_quality['value'] = (
        surface_water_quality['value']
        .apply(lambda x: x.rstrip('0').rstrip('.') if '.' in x else x)
    )
    # Replace string representations of 'nan' and '*' with None to standardize missing values
    surface_water_quality = surface_water_quality.replace({'nan': None, '*': None})
    return surface_water_quality


async def _fetch_surface_water_quality_for_site(sem: asyncio.Semaphore, site_id: str) -> Optional[pd.DataFrame]:
    """
    Fetch surface water quality data from ECAN for the specified site.

    Parameters
    ----------
    sem : asyncio.Semaphore
        A semaphore to limit the number of concurrent requests.
    site_id : str
        The unique site ID of the surface water site for which the data is to be fetched.

    Returns
    -------
    Optional[pd.DataFrame]
        A DataFrame containing surface water quality data from ECAN for the requested site,
        or `None` if the data is unavailable or the site ID is invalid.

    Raises
    ------
    aiohttp.ClientResponseError
        If the request fails with a non-internal server-related HTTP error.
    """
    # Construct the URL for fetching surface water quality data using the provided site ID
    url = f"https://www.ecan.govt.nz/data/water-quality-data/exportallsample/{site_id}"
    try:
        async with sem:
            async with aiohttp.ClientSession() as session:
                # Send a GET request to the constructed URL, and raise an exception if the response status is not 200
                async with session.get(url, raise_for_status=True) as resp:
                    # Read the response text and load it into a DataFrame, skipping the first two rows
                    csv_text = await resp.text()
                    resp_df = pd.read_csv(StringIO(csv_text), skiprows=2)
                    return resp_df
    except aiohttp.ClientResponseError as e:
        # Log a warning and return None if a server error (500) occurs, indicating that data for the site is unavailable
        if e.status == HTTPStatus.INTERNAL_SERVER_ERROR:
            log.warning(f"Surface water quality data for site {site_id} cannot be found.")
            return None
        # For any other error, re-raise the original ClientResponseError
        else:
            raise


async def fetch_surface_water_quality_for_aoi(surface_water_site_ids: List[str]) -> pd.DataFrame:
    """
    Fetch surface water quality data from ECAN for a list of specified surface water sites.

    Parameters
    ----------
    surface_water_site_ids : List[str]
        A list of unique site IDs of the surface water sites for which the data are to be fetched.

    Returns
    -------
    pd.DataFrame
        A DataFrame containing surface water quality data from ECAN for the requested sites.
    """
    # Create a semaphore to limit the number of concurrent requests to 15
    sem = asyncio.Semaphore(15)
    tasks = []
    async with asyncio.TaskGroup() as tg:
        # Create a task for each site ID to fetch its surface water quality data
        for site_id in surface_water_site_ids:
            task = tg.create_task(_fetch_surface_water_quality_for_site(sem, site_id))
            tasks.append(task)
    # Retrieve results from all tasks and concatenate them into a single DataFrame
    results = [task.result() for task in tasks]
    surface_water_quality = pd.concat(results, ignore_index=True)
    # Clean and process the raw surface water quality data retrieved from ECAN
    surface_water_quality = clean_raw_surface_water_quality(surface_water_quality)
    return surface_water_quality


def get_surface_water_quality_with_geom(engine: Engine, catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Fetch surface water quality data from ECAN for the specified catchment area.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the surface water quality data from ECAN for the requested catchment area.

    Raises
    ------
    NoSurfaceWaterSitesException
        If no surface water sites are found within the requested catchment area.
    """
    log.info("Fetching surface water quality data from ECAN.")
    # Retrieve surface water site data from the database for the requested catchment area
    surface_water_sites = get_surface_water_sites_from_db(engine, catchment_area)
    # If no sites are found within the catchment area, raise an exception
    if surface_water_sites.empty:
        raise NoSurfaceWaterSitesException("No surface water sites found within the requested catchment area.")
    # If sites are found, get a list of unique site IDs for fetching surface water quality data
    surface_water_site_ids = surface_water_sites["site_id"].unique().tolist()
    # Fetch surface water quality data from ECAN for the identified sites within the catchment area
    water_quality_data = asyncio.run(fetch_surface_water_quality_for_aoi(surface_water_site_ids))
    # Merge the fetched water quality data with site geometries to add geometric information
    sites_geometry = surface_water_sites[["site_id", "geometry"]]
    water_quality_with_geom = water_quality_data.merge(sites_geometry, how="left", on="site_id", validate="many_to_one")
    # Convert the merged result into a GeoDataFrame and reset the index
    water_quality_with_geom = gpd.GeoDataFrame(water_quality_with_geom).reset_index(drop=True)
    return water_quality_with_geom


def get_surface_water_quality_from_db(engine: Engine, catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Retrieve surface water quality data from the database for the specified catchment area.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the retrieved surface water quality data for the requested catchment area.

    Raises
    ------
    NoSurfaceWaterQualityException
        If the `surface_water_quality` table does not exist in the database.
    """
    # Raise an exception if the `surface_water_quality` table does not exist in the database
    if not check_table_exists(engine, "surface_water_quality"):
        raise NoSurfaceWaterQualityException("No surface water quality data is available in the database.")
    # Extract the geometry of the catchment area and its corresponding CRS
    catchment_polygon = catchment_area["geometry"][0]
    catchment_crs = catchment_area.crs.to_epsg()
    # Query to retrieve surface water quality data that intersects with the catchment polygon
    command_text = """
        SELECT *
        FROM surface_water_quality AS swq
        WHERE ST_Intersects(swq.geometry, ST_GeomFromText(:catchment_polygon, :catchment_crs));
        """
    query = text(command_text).bindparams(
        catchment_polygon=str(catchment_polygon),
        catchment_crs=str(catchment_crs)
    )
    # Execute the query and create a GeoDataFrame from the result
    swq_data = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry")
    return swq_data


def get_surface_water_quality_not_in_db(engine: Engine, catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Retrieve surface water quality data from ECAN for the specified catchment area that is not already present
    in the existing database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing surface water quality data from ECAN for the requested catchment area that is
        not already present in the existing database.
    """  # noqa: D400
    # Retrieve existing surface water quality data from the database for the requested catchment area
    water_quality_exist = get_surface_water_quality_from_db(engine, catchment_area)
    # Fetch surface water quality data from ECAN for the requested catchment area
    water_quality_new = get_surface_water_quality_with_geom(engine, catchment_area)
    # Identify records in the new surface water quality data that are not present in the existing database
    water_quality_not_in_db = pd.concat([water_quality_exist, water_quality_new]).drop_duplicates(keep=False)
    return water_quality_not_in_db


def store_surface_water_quality_to_db(engine: Engine, catchment_area: gpd.GeoDataFrame) -> None:
    """
    Fetch surface water quality data from ECAN for the specified catchment area and store it in the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    """
    # Define the table name for storing the surface water quality data
    table_name = "surface_water_quality"
    # Check if the table already exists in the database
    if check_table_exists(engine, table_name):
        try:
            # Retrieve surface water quality data from ECAN for the requested catchment area
            # that is not already present in the existing database
            water_quality_not_in_db = get_surface_water_quality_not_in_db(engine, catchment_area)
            # Check if any new surface water quality data was retrieved
            if water_quality_not_in_db.empty:
                # If no new data is found, log a message indicating that no new data was found
                log.info("No new surface water quality data found for the requested catchment area.")
            else:
                # If new data is found, add it to the relevant table in the database
                log.info(f"Adding '{table_name}' for sites within the requested catchment area to the database.")
                water_quality_not_in_db.to_postgis(table_name, engine, index=False, if_exists="append")
                log.info(f"Successfully added '{table_name}' to the database.")
        except NoSurfaceWaterSitesException:
            # If no sites are found, log a message indicating that no water quality data is available
            log.info("No surface water quality data found for the requested catchment area.")
    else:
        try:
            # Fetch surface water quality data from ECAN for the requested catchment area
            surface_water_quality = get_surface_water_quality_with_geom(engine, catchment_area)
            # If data is found, add it to the relevant table in the database
            log.info(f"Adding '{table_name}' for sites within the requested catchment area to the database.")
            surface_water_quality.to_postgis(table_name, engine, index=False, if_exists="replace")
            log.info(f"Successfully added '{table_name}' to the database.")
        except NoSurfaceWaterSitesException:
            # If no sites are found, log a message indicating that no water quality data is available
            log.info("No surface water quality data found for the requested catchment area.")


def get_req_surface_water_quality_from_db(
        engine: Engine,
        catchment_area: gpd.GeoDataFrame,
        year: Optional[int] = None) -> gpd.GeoDataFrame:
    """
    Retrieve the latest requested surface water quality data from the database for the specified catchment area.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.
    year : Optional[int] = None
        The year from which to include the latest surface water quality data for sites within the specified
        catchment area. If not provided or set to `None`, all latest data will be included.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the latest requested surface water quality data from the database for the
        specified catchment area, or an empty GeoDataFrame if no records are found.
    """
    log.info("Retrieving requested surface water quality data from the database.")

    try:
        # Retrieve surface water quality data from the database for the requested catchment area
        swq = get_surface_water_quality_from_db(engine, catchment_area)

        # Check if the retrieved data is empty
        if swq.empty:
            # Return None if no data is available
            log.info(
                "No surface water quality data is available for the specified catchment area.")
            return gpd.GeoDataFrame()
        else:
            # Group the data by site_id to obtain the latest collection_date for each site
            latest_dates = swq.groupby('site_id')['collection_date'].max().reset_index()
            # Merge to obtain all records with the latest collection_date for each site
            requested_records = latest_dates.merge(swq, on=['site_id', 'collection_date'], how='left')
            # Check if a specific year is provided to filter the data
            if year is not None:
                # Filter for records where the year of collection_date is greater than or equal to the requested year
                requested_records = requested_records[requested_records['collection_date'].dt.year >= year]
            # Convert the result into a GeoDataFrame and reset the index
            requested_records = gpd.GeoDataFrame(requested_records).reset_index(drop=True)
            # Log a message if no records are found
            if requested_records.empty:
                log.info(
                    "No requested surface water quality data is available for the specified catchment area.")
                return gpd.GeoDataFrame()
            # Log a success message and return the records if found
            log.info("Retrieved the requested surface water quality data from the database.")
            return requested_records

    except NoSurfaceWaterQualityException as e:
        # Log a message to indicate that surface water quality data is absent in the database
        log.info(e)
        return gpd.GeoDataFrame()
