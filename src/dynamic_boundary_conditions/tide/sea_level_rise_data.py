# -*- coding: utf-8 -*-
"""
This script handles the fetching of sea level rise data from the NZ SeaRise Takiwa website, storing the data in the
database, and retrieving the closest sea level rise data from the database for all locations in the provided tide data.
"""

import logging
import platform
import subprocess
import time
from io import StringIO

import geopandas as gpd
import pandas as pd
import requests
from requests.models import Response
from requests.structures import CaseInsensitiveDict
from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from sqlalchemy.engine import Engine

from src.digitaltwin import tables

log = logging.getLogger(__name__)


def initialize_headless_webdriver() -> WebDriver:
    """
    Initializes a headless WebDriver instance based on the operating system.

    Returns
    -------
    WebDriver
        A headless WebDriver instance (Chrome for Windows, Firefox for other operating system).
    """
    # Create a webdriver, Chrome for windows or Firefox for other operating system
    operating_system = platform.system()
    if operating_system == "Windows":
        # Create a ChromeOptions object to customize the settings for the Chrome WebDriver
        chrome_options = webdriver.ChromeOptions()
        # Enable headless mode for Chrome (no visible browser window)
        chrome_options.add_argument("--headless")
        # Initialize a new instance of the Chrome WebDriver using the customized ChromeOptions
        driver = webdriver.Chrome(options=chrome_options)
    else:
        # Initialise a Firefox browser since the Chrome browser was not successfully being found by selenium in linux
        firefox_options = webdriver.FirefoxOptions()
        # Enable headless mode for Firefox (no visible browser window)
        firefox_options.add_argument("--headless")
        # Find driver_location with linux command `which` since selenium did not always find the correct binary
        driver_location = subprocess.check_output("which geckodriver", shell=True,
                                                  stderr=subprocess.STDOUT).decode().strip()
        # Create firefox with explicit driver_location since selenium does not always find the correct driver binary
        firefox_service = webdriver.FirefoxService(executable_path=driver_location)
        # Create firefox webdriver
        driver = webdriver.Firefox(options=firefox_options, service=firefox_service)
    return driver


def fetch_slr_data_from_takiwa() -> gpd.GeoDataFrame:
    """
    Fetch sea level rise (SLR) data from the NZ SeaRise Takiwa website.

    Returns
    -------
    gpd.GeoDataFrame
        Sea level rise (SLR) data for New Zealand.
    """
    # Log that the fetching of sea level rise data from NZ SeaRise Takiwa has started
    log.info("Fetching 'sea_level_rise' data from NZ SeaRise Takiwa.")
    # Initializes a headless WebDriver instance based on the operating system
    driver = initialize_headless_webdriver()
    # Open the specified website in the browser
    driver.get("https://searise.takiwa.co/map/6245144372b819001837b900")
    # Add a 1-second delay to ensure that the website is open before downloading
    time.sleep(1)
    # Find and click the "Accept" button on the web page
    driver.find_element(By.CSS_SELECTOR, "button.ui.green.basic.button").click()
    # Find and click "Download"
    driver.find_element(By.ID, "container-control-text-6268d9223c91dd00278d5ecf").click()
    # Find and click "Download Regional Data"
    [element.click() for element in driver.find_elements(By.TAG_NAME, "h5") if element.text == "Download Regional Data"]
    # Identify links to all the regional data files on the webpage
    elements = driver.find_elements(By.CSS_SELECTOR, "div.content.active a")
    # Create an empty DataFrame to store the SLR data
    slr_data = pd.DataFrame()
    # Iterate through the identified links and retrieve the CSV content into memory
    for element in elements:
        # Scroll down the div to the link. Required for firefox browser
        driver.execute_script("arguments[0].scrollIntoView(true);", element)
        # Get the URL of the CSV file to fetch
        csv_url = element.get_attribute("href")
        # Define custom headers to mimic a browser's user-agent
        headers = CaseInsensitiveDict()
        headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)\
                Chrome/96.0.4664.110 Safari/537.36"
        # Make a GET request to fetch the CSV content into memory with custom headers
        response = requests.get(csv_url, headers=headers)
        # Extract the text content from the response and parse it into a DataFrame using pandas
        resp_df = pd.read_csv(StringIO(response.text))
        # Extract region name from file name and add it as a new column to the DataFrame
        resp_df['region'] = extract_region_name(response)
        # Concatenate the retrieved data with the existing SLR data DataFrame
        slr_data = pd.concat([slr_data, resp_df])
    # Quit the WebDriver, closing the browser
    driver.quit()
    # Log that the data have been successfully loaded
    log.info("Successfully fetched 'sea_level_rise' data from NZ SeaRise Takiwa.")
    # Enhance SLR data by incorporating geographical geometry and converting column names to lowercase
    slr_nz = prep_slr_geo_data(slr_data)
    return slr_nz


def extract_region_name(response: Response) -> str:
    """
    Extracts the region name from the filename specified in the Content-Disposition header of the provided response.

    Parameters
    ----------
    response : Response
        The HTTP response object containing the Content-Disposition header.

    Returns
    -------
    str
        The extracted region name from the filename.
    """
    # Extract the Content-Disposition header from the response to get the file name
    content_disposition = response.headers['Content-Disposition']
    # Find the index where the 'filename=' starts
    file_name_index = content_disposition.find('filename=')
    # Extract the file name from the Content-Disposition header
    file_name = content_disposition[file_name_index + len('filename='):]
    # Remove any surrounding double quotes from the file name
    file_name = file_name.strip('"')
    # Find the starting index of the region name within the file name
    start_index = file_name.find('projections_') + len('projections_')
    # Find the ending index of the region name within the file name
    end_index = file_name.find('_region')
    # Extract the region name from the file name
    region_name = file_name[start_index:end_index]
    return region_name


def prep_slr_geo_data(slr_data: pd.DataFrame) -> gpd.GeoDataFrame:
    """
    Enhance sea level rise (SLR) data by incorporating geographical geometry based on longitude and latitude,
    creating Point geometries, and ensure consistency by converting all column names to lowercase.

    Parameters
    ----------
    slr_data : pd.DataFrame
        Sea level rise (SLR) data containing columns 'lon' and 'lat' for longitude and latitude respectively.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing sea level rise (SLR) data with geometry information.
    """
    # Create Point geometries from latitude and longitude
    geometry = gpd.points_from_xy(slr_data['lon'], slr_data['lat'], crs=4326)
    # Create a GeoDataFrame from the SLR data and geometry
    slr_nz = gpd.GeoDataFrame(slr_data, geometry=geometry)
    # Convert all column names to lowercase
    slr_nz.columns = slr_nz.columns.str.lower()
    return slr_nz


def store_slr_data_to_db(engine: Engine) -> None:
    """
    Store sea level rise data to the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Define the table name for storing the sea level rise data
    table_name = "sea_level_rise"
    # Check if the table already exists in the database
    if tables.check_table_exists(engine, table_name):
        log.info(f"'{table_name}' data already exists in the database.")
    else:
        # Fetch sea level rise (SLR) data from the NZ SeaRise Takiwa website
        slr_nz = fetch_slr_data_from_takiwa()
        # Store the sea level rise data to the database table
        log.info(f"Adding '{table_name}' data to the database.")
        slr_nz.to_postgis(table_name, engine, index=False, if_exists="replace")


def get_closest_slr_data(engine: Engine, single_query_loc: pd.Series) -> gpd.GeoDataFrame:
    """
    Retrieve the closest sea level rise data for a single query location from the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    single_query_loc : pd.Series
        Pandas Series containing the location coordinate and additional information used for retrieval.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the closest sea level rise data for the query location from the database.
    """
    # Create a GeoDataFrame with the query location geometry
    query_loc_geom = gpd.GeoDataFrame(geometry=[single_query_loc["geometry"]], crs=4326)
    # Convert the query location geometry to the desired coordinate reference system (CRS)
    query_loc_geom = query_loc_geom.to_crs(2193).reset_index(drop=True)
    # Prepare the query to retrieve sea level rise data based on the query location.
    # The subquery calculates the distances between the query location and each location in the 'sea_level_rise' table.
    # It then identifies the location with the shortest distance, indicating the closest location to the query location,
    # and retrieves the 'siteid' associated with that closest location, along with its corresponding distance value.
    # The outer query joins the sea_level_rise table with the inner subquery, merging the results to retrieve the
    # relevant data, which includes the calculated distance. By matching the closest location's 'siteid' from the
    # inner subquery with the corresponding data in the sea_level_rise table using the JOIN clause, the outer query
    # obtains the sea level rise data for the closest location, along with its associated distance value.
    query = f"""
    SELECT slr.*, distances.distance
    FROM sea_level_rise AS slr
    JOIN (
        SELECT siteid,
        ST_Distance(ST_Transform(geometry, 2193), ST_GeomFromText('{query_loc_geom["geometry"][0]}', 2193)) AS distance
        FROM sea_level_rise
        ORDER BY distance
        LIMIT 1
    ) AS distances ON slr.siteid = distances.siteid;
    """
    # Execute the query and retrieve the data as a GeoDataFrame
    query_data = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry")
    # Add the position information to the retrieved data
    query_data["position"] = single_query_loc["position"]
    return query_data


def get_slr_data_from_db(engine: Engine, tide_data: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Retrieve the closest sea level rise data from the database for all locations in the provided tide data.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    tide_data : gpd.GeoDataFrame
        A GeoDataFrame containing tide data with added time information (seconds, minutes, hours) and location details.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the closest sea level rise data for all locations in the tide data.
    """
    log.info("Retrieving 'sea_level_rise' data for the requested catchment area from the database.")
    # Select unique query locations from the tide data
    tide_data_loc = tide_data[['position', 'geometry']].drop_duplicates()
    # Initialize an empty GeoDataFrame to store the closest sea level rise data for all locations
    slr_data = gpd.GeoDataFrame()
    # Iterate over each query location
    for _, row in tide_data_loc.iterrows():
        # Retrieve the closest sea level rise data from the database for the current query location
        query_loc_data = get_closest_slr_data(engine, row)
        # Add a column to the retrieved data to store the geometry of the tide data location
        query_loc_data["tide_data_loc"] = row["geometry"]
        # Concatenate the closest sea level rise data for the query location with the overall sea level rise data
        slr_data = pd.concat([slr_data, query_loc_data])
    # Reset the index of the closest sea level rise data
    slr_data = gpd.GeoDataFrame(slr_data).reset_index(drop=True)
    return slr_data
