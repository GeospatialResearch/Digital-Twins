# -*- coding: utf-8 -*-
"""
This script handles the downloading and reading of sea level rise data from the NZ Sea level rise datasets,
storing the data in the database, and retrieving the closest sea level rise data from the database for all locations
in the provided tide data.
"""

import logging
import os
import pathlib
import platform
import subprocess
import time

import geopandas as gpd
import pandas as pd
import pyarrow.csv as csv
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from sqlalchemy.engine import Engine

from src import config
from src.digitaltwin import tables

log = logging.getLogger(__name__)


def download_slr_data_files_from_takiwa(slr_data_dir: pathlib.Path) -> None:
    """
    Download regional sea level rise (SLR) data files from the NZ SeaRise Takiwa website.

    Parameters
    ----------
    slr_data_dir : pathlib.Path
        The directory where the downloaded sea level rise data files will be saved.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Check if the directory exists and, if so, delete all files within it
    if slr_data_dir.exists():
        [slr_file.unlink() for slr_file in slr_data_dir.glob("*")]
    # Create the directory if it does not already exist
    else:
        slr_data_dir.mkdir(parents=True, exist_ok=True)
    # Log that the downloading of regional sea level rise data files from NZ SeaRise Takiwa has started
    log.info("Downloading regional 'sea_level_rise' data files from NZ SeaRise Takiwa.")
    # Create a webdriver, Chrome for windows or Firefox for other.
    operating_system = platform.system()
    if operating_system == "Windows":
        # Initialize a ChromeOptions instance to customize the Chrome WebDriver settings
        chrome_options = webdriver.ChromeOptions()
        # Enable headless mode for Chrome (no visible browser window)
        chrome_options.add_argument("--headless")
        # Define the download directory preference for downloaded files
        prefs = {"download.default_directory": str(slr_data_dir.resolve())}
        # Apply the download directory preference to ChromeOptions
        chrome_options.add_experimental_option("prefs", prefs)
        # Create the webdriver using Chrome
        driver = webdriver.Chrome(options=chrome_options)

    else:
        # Initialise a firefox browser since the chrome browser was not successfully being found by selenium in linux
        firefox_options = webdriver.FirefoxOptions()
        # Enable headless mode for Chrome (no visible browser window)
        firefox_options.add_argument("--headless")
        # Define the download directory preference for downloaded files
        firefox_options.set_preference("browser.download.folderList", 2)
        firefox_options.set_preference("browser.download.dir", str(slr_data_dir.resolve()))
        firefox_options.set_preference("browser.download.manager.showWhenStarting", False)
        # When downloading files, do not ask user for confirmation or location.
        firefox_options.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/octet-stream")
        # Find driver_location with linux command `which` since selenium did not always find the correct binary
        driver_location = subprocess.check_output("which geckodriver", shell=True,
                                                  stderr=subprocess.STDOUT).decode().strip()
        # Create firefox with explicit driver_location since selenium does not always find the correct driver binary
        firefox_service = webdriver.FirefoxService(executable_path=driver_location)
        # Create firefox webdriver
        driver = webdriver.Firefox(options=firefox_options, service=firefox_service)

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
    # Iterate through the identified links and simulate a click action to trigger the download
    for element in elements:
        # Scroll down the div to the link. Required for firefox browser
        driver.execute_script("arguments[0].scrollIntoView(true);", element)
        # Click the download link
        ActionChains(driver).move_to_element(element).click().perform()
        # Wait a short delay before clicking again so that the download starts.
        time.sleep(0.5)
    # Add a 3-second delay to ensure all downloads are complete before quitting the browser
    time.sleep(3)
    # Quit the WebDriver, closing the browser
    driver.quit()
    # If running this from windows within a WSL directory, Zone.Identifier files are created and must be removed.
    for zone_identifier_file in slr_data_dir.glob("*Zone.identifier"):
        os.remove(zone_identifier_file)
    # Check that the number of downloaded files matches the number of links on the webpage
    slr_dir_files = list(slr_data_dir.glob("*"))
    if len(slr_dir_files) != len(elements):
        logging.debug(f"slr_dir_files = {slr_dir_files}")
        logging.debug(f"elements = {elements}")
        raise ValueError(f"The number of files in slr_data_dir ({len(slr_dir_files)})"
                         f" does not match the number of datasets found on the web page ({len(elements)})")
    # Log that the files have been successfully downloaded
    log.info("Successfully downloaded regional 'sea_level_rise' data files from NZ SeaRise Takiwa.")


def read_slr_data_from_files(slr_data_dir: pathlib.Path) -> gpd.GeoDataFrame:
    """
    Read sea level rise data from the NZ Sea level rise datasets and return a GeoDataFrame.

    Parameters
    ----------
    slr_data_dir : pathlib.Path
        The directory containing the downloaded sea level rise data files.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the sea level rise data from the NZ Sea level rise datasets.

    Raises
    ------
    FileNotFoundError
        If the sea level rise data directory does not exist or if there are no CSV files in the specified directory.
    """
    # Check if the sea level rise data directory exists
    if not slr_data_dir.exists():
        raise FileNotFoundError(f"'sea_level_rise' data directory not found: '{slr_data_dir}'.")
    # Check if there are any CSV files in the specified directory
    if not any(slr_data_dir.glob("*.csv")):
        raise FileNotFoundError(f"'sea_level_rise' data files not found in: '{slr_data_dir}'")
    # Create an empty list to store the sea level rise datasets
    slr_nz_list = []
    # Loop through each CSV file in the specified directory
    for file_path in slr_data_dir.glob("*.csv"):
        # Read the CSV file into a pandas DataFrame using pyarrow
        slr_region = csv.read_csv(file_path).to_pandas()
        # Extract the region name from the file name and add it as a new column in the DataFrame
        file_name = file_path.stem
        start_index = file_name.find('projections_') + len('projections_')
        end_index = file_name.find('_region')
        region_name = file_name[start_index:end_index]
        slr_region['region'] = region_name
        # Append the DataFrame to the list
        slr_nz_list.append(slr_region)
        # Log that the file has been successfully loaded
        log.info(f"Successfully loaded the '{file_path.name}' data file.")
    # Concatenate all the dataframes in the list and add geometry column
    slr_nz = pd.concat(slr_nz_list, axis=0).reset_index(drop=True)
    geometry = gpd.points_from_xy(slr_nz['lon'], slr_nz['lat'], crs=4326)
    slr_nz_with_geom = gpd.GeoDataFrame(slr_nz, geometry=geometry)
    # Convert all column names to lowercase
    slr_nz_with_geom.columns = slr_nz_with_geom.columns.str.lower()
    return slr_nz_with_geom


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
        # Get the data directory and append "slr_data" to specify the sea level rise data directory
        slr_data_dir = config.get_env_variable("DATA_DIR", cast_to=pathlib.Path) / "slr_data"
        # Download regional sea level rise (SLR) data files from the NZ SeaRise Takiwa website
        download_slr_data_files_from_takiwa(slr_data_dir)
        # Read sea level rise data from the NZ Sea level rise datasets
        slr_nz = read_slr_data_from_files(slr_data_dir)
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
