# -*- coding: utf-8 -*-
"""
@Script name: hirds_depth_data_to_db.py
@Description: Store rainfall data of all the sites within the catchment area in the database.
@Author: pkh35
@Date: 20/01/2022
@Last modified by: sli229
@Last modified date: 27/09/2022
"""

import re
import pandas as pd
import geopandas as gpd
import sqlalchemy
import pathlib
import logging
from typing import List, Tuple
from shapely.geometry import Polygon
from src.dynamic_boundary_conditions import rain_depth_data_from_hirds
from src.digitaltwin import setup_environment
from src.dynamic_boundary_conditions import hyetograph

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def check_table_exists(engine, db_table_name: str) -> bool:
    """
    Check if table exists in the database.

    Parameters
    ----------
    engine
        Engine used to connect to the database.
    db_table_name : str
        Database table name.
    """
    insp = sqlalchemy.inspect(engine)
    return insp.has_table(db_table_name, schema="public")


def get_sites_id_in_catchment(engine, catchment_polygon: Polygon) -> List[str]:
    """
    Get rainfall sites ids within the catchment area from the 'rainfall_sites' table in the database.

    Parameters
    ----------
    engine
        Engine used to connect to the database.
    catchment_polygon : Polygon
        Desired catchment area.
    """
    query = f"""SELECT * FROM rainfall_sites AS rs
        WHERE ST_Intersects(rs.geometry, ST_GeomFromText('{catchment_polygon}', 4326))"""
    sites_in_catchment = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry", crs=4326)
    sites_id_in_catchment = sites_in_catchment["site_id"].tolist()
    return sites_id_in_catchment


def get_sites_id_not_in_db(engine, sites_id_in_catchment: List[str]) -> List[str]:
    """
    Get the list of rainfall sites ids that are in the catchment area but are not in the database.

    Parameters
    ----------
    engine
        Engine used to connect to the database.
    sites_id_in_catchment : List[str]
        Rainfall sites ids within the catchment area.
    """
    query = "SELECT DISTINCT site_id FROM rainfall_depth;"
    # Get dataframe of sites in the database
    sites_id_in_db = pd.read_sql_query(query, engine)
    # Convert dataframe to list of sites in the database
    sites_id_in_db = sites_id_in_db["site_id"].tolist()
    # yields the elements in `sites_id_in_catchment` that are NOT in `sites_id_in_db`
    sites_id_not_in_db = list(set(sites_id_in_catchment).difference(sites_id_in_db))
    return sites_id_not_in_db


def get_layout_structure_of_csv(filepath) -> List[Tuple[int, float, str]]:
    """
    Read the rainfall data CSV file and return a list of tuples (skip_rows, rcp, time_period) of its layout structure.

    Parameters
    ----------
    filepath
        The file path of the downloaded rainfall data CSV files.
    """
    skip_rows = []
    rcp = []
    time_period = []
    # Read file line by line with a for loop
    with open(filepath) as file:
        for index, line in enumerate(file):
            # Get lines that contain "(mm) ::" for depth data or "(mm/hr) ::" for intensity data
            if (line.find("(mm) ::") != -1) or (line.find("(mm/hr) ::") != -1):
                # Add the row number to skip_rows list
                skip_rows.append(index + 1)
                # Add the obtained rcp and time_period values to list
                rcp_result = re.search(r"(\d*\.\d*)", line)
                period_result = re.search(r"(\d{4}-\d{4})", line)
                if rcp_result or period_result is not None:
                    rcp.append(float(rcp_result[0]))
                    time_period.append(period_result[0])
                else:
                    rcp.append(float('nan'))
                    time_period.append(None)
    # Merge the three different lists into one list of tuples
    layout_structure = list(zip(skip_rows, rcp, time_period))
    return layout_structure


def get_data_from_csv(filepath, site_id: str, skip_rows: int, rcp: float, time_period: str) -> pd.DataFrame:
    """
    Read the rainfall data CSV file and return the required data in Pandas DataFrame format.

    Parameters
    ----------
    filepath
        The file path of the downloaded rainfall data CSV files.
    site_id : str
        HIRDS rainfall site id.
    skip_rows : int
        Number of lines to skip at the start of the CSV file.
    rcp : float
        There are four different representative concentration pathways (RCPs), and abbreviated as RCP2.6, RCP4.5,
        RCP6.0 and RCP8.5, in order of increasing radiative forcing by greenhouse gases.
    time_period : str
        Rainfall estimates for two future time periods (e.g. 2031-2050 or 2081-2100) for four RCPs.
    """
    rainfall_data = pd.read_csv(filepath, skiprows=skip_rows, nrows=12)
    rainfall_data.insert(0, "site_id", site_id)
    rainfall_data.insert(1, "rcp", rcp)
    rainfall_data.insert(2, "time_period", time_period)
    rainfall_data.columns = rainfall_data.columns.str.lower()
    return rainfall_data


def add_rain_depth_data_to_db(engine, site_id: str, path, idf: bool):
    """
    Store each site's rainfall data in the database.
    Each CSV file contains historical and future forecasted rainfall data for various rcp, time periods and durations.
    To view the CSV file, go to https://hirds.niwa.co.nz/, select a site and generate a report,
    there are rainfall depths and rainfall intensities data for different RCP Scenarios.
    To understand the structure of the CSV file, download the spreadsheet.

    Parameters
    ----------
    engine
        Engine used to connect to the database.
    site_id : str
        HIRDS rainfall site id.
    path
        The file path of where the downloaded rainfall data CSV files are stored.
    """
    rain_table_name = db_rain_table_name(idf)
    filename = pathlib.Path(f"{site_id}_{rain_table_name}.csv")
    filepath = (path / filename)

    layout_structure = get_layout_structure_of_csv(filepath)

    for (skip_rows, rcp, time_period) in layout_structure:
        site_data = get_data_from_csv(filepath, site_id, skip_rows=skip_rows, rcp=rcp, time_period=time_period)
        site_data.to_sql(rain_table_name, engine, index=False, if_exists="append")
    log.info(f"Added {rain_table_name} data for site {site_id} to database")


def add_each_site_rain_depth_data(engine, sites_id_list: List[str], path: str, idf: bool):
    """
    Loop through all the sites in the sites_id_list, download and store each site's rainfall data as a CSV file
    in the desired file path, and then read the CSV files to store the rainfall data in the database.

    Parameters
    ----------
    engine
        Engine used to connect to the database.
    sites_id_list : List[str]
        Rainfall sites' ids.
    path
        The file path of where the downloaded rainfall data CSV files are stored.
    idf : bool
        Set to False for rainfall depth data, and True for rainfall intensity data.
    """
    for site_id in sites_id_list:
        rain_depth_data_from_hirds.store_data_to_csv(site_id, path, idf)
        add_rain_depth_data_to_db(engine, site_id, path, idf)


def db_rain_table_name(idf: bool) -> str:
    table_name = "rainfall_depth" if idf is False else "rainfall_intensity"
    return table_name


def rain_depths_to_db(engine, catchment_polygon: Polygon, path, idf: bool):
    """
    Store rainfall data of all the sites within the catchment area in the database.

    Parameters
    ----------
    engine
        Engine used to connect to the database.
    catchment_polygon : Polygon
        Desired catchment area.
    path
         The file path of where the downloaded rainfall data CSV files are stored.
    idf : bool
        Set to False for rainfall depth data, and True for rainfall intensity data.
    """
    sites_id_in_catchment = get_sites_id_in_catchment(engine, catchment_polygon)
    rain_table_name = db_rain_table_name(idf)
    # check if 'rainfall_depth' or 'rainfall_intensity' table is already in the database
    if check_table_exists(engine, rain_table_name):
        sites_id_not_in_db = get_sites_id_not_in_db(engine, sites_id_in_catchment)
        # Check if sites_id_not_in_db is not empty
        if sites_id_not_in_db:
            add_each_site_rain_depth_data(engine, sites_id_not_in_db, path, idf)
        else:
            log.info("Sites for the requested catchment already available in the database.")
    else:
        # check if sites_id_in_catchment is not empty
        if sites_id_in_catchment:
            add_each_site_rain_depth_data(engine, sites_id_in_catchment, path, idf)
        else:
            log.info("There are no sites within the requested catchment area, select a wider area.")


def main():
    catchment_file = pathlib.Path(r"src\dynamic_boundary_conditions\catchment_polygon.shp")
    file_path_to_store = pathlib.Path(r"U:\Research\FloodRiskResearch\DigitalTwin\hirds_rainfall_data")
    engine = setup_environment.get_database()
    catchment_polygon = hyetograph.catchment_area_geometry_info(catchment_file)
    # Set idf to False for rain depth data and to True for rain intensity data
    rain_depths_to_db(engine, catchment_polygon, file_path_to_store, idf=False)
    rain_depths_to_db(engine, catchment_polygon, file_path_to_store, idf=True)


if __name__ == "__main__":
    main()
