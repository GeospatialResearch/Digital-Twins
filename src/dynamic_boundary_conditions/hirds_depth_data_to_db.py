# -*- coding: utf-8 -*-
"""
Created on Thu Jan 20 15:09:11 2022

@author: pkh35
"""

import re
import pandas as pd
import geopandas as gpd
import sqlalchemy
import pathlib
import logging
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
    """Check if table exists in the database."""
    insp = sqlalchemy.inspect(engine)
    return insp.has_table(db_table_name, schema="public")


def get_sites_id_in_catchment(engine, catchment_polygon: Polygon) -> list:
    """Get rainfall sites id within the catchment area from the 'rainfall_sites' table in the database."""
    query = f"""SELECT * FROM rainfall_sites AS rs
        WHERE ST_Intersects(rs.geometry, ST_GeomFromText('{catchment_polygon}', 4326))"""
    sites_in_catchment = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry", crs=4326)
    sites_id_in_catchment = sites_in_catchment["site_id"].tolist()
    return sites_id_in_catchment


def get_sites_id_not_in_db(engine, sites_id_in_catchment: list) -> list:
    """Get the list of sites that are in the catchment area but are not available in the database."""
    query = "SELECT DISTINCT site_id FROM rainfall_depth;"
    # Get dataframe of sites in the database
    sites_id_in_db = pd.read_sql_query(query, engine)
    # Convert dataframe to list of sites in the database
    sites_id_in_db = sites_id_in_db["site_id"].tolist()
    # yields the elements in `sites_id_in_catchment` that are NOT in `sites_id_in_db`
    sites_id_not_in_db = list(set(sites_id_in_catchment).difference(sites_id_in_db))
    return sites_id_not_in_db


def get_layout_structure_of_csv(filepath) -> list:
    """Read the csv file of each site's rainfall data and return a list of tuples (skip_rows, rcp, time_period)
    of its layout structure"""
    skip_rows = []
    rcp = []
    time_period = []
    # Read file line by line with a for loop
    with open(filepath) as file:
        for index, line in enumerate(file):
            # Get lines that contain "(mm) ::"
            if (line.find("(mm) ::") != -1) or (line.find("(mm/hr) ::") != -1):
                # add the row number to skip_rows list
                skip_rows.append(index + 1)
                # add the obtained rcp and time_period values to list
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
    """Read the csv files of the different sites rainfall data and return a dataframe."""
    rainfall_data = pd.read_csv(filepath, skiprows=skip_rows, nrows=12)
    rainfall_data.insert(0, "site_id", site_id)
    rainfall_data.insert(1, "rcp", rcp)
    rainfall_data.insert(2, "time_period", time_period)
    rainfall_data.columns = rainfall_data.columns.str.lower()
    return rainfall_data


def add_rain_depth_data_to_db(engine, site_id: str, path):
    """Store each site's rainfall data in the database. Each csv file contains historical and future forecasted
    rainfall data for various rcp, time periods and durations.
    To view the csv file, go to : https://hirds.niwa.co.nz/, select a site and generate a report,
    there are rainfall depths and rainfall intensities data for different RCP Scenarios.
    To understand the structure of the CSV file, download the spreadsheet.
    """
    filename = pathlib.Path(f"{site_id}_rain_depth.csv")
    filepath = (path / filename)

    layout_structure = get_layout_structure_of_csv(filepath)

    for (skip_rows, rcp, time_period) in layout_structure:
        site_data = get_data_from_csv(filepath, site_id, skip_rows=skip_rows, rcp=rcp, time_period=time_period)
        site_data.to_sql("rainfall_depth", engine, index=False, if_exists="append")
    log.info(f"Added rainfall depth data for site {site_id} to database")


def add_each_site_rain_depth_data(engine, sites_id_list: list, path: str, idf: str):
    for site_id in sites_id_list:
        rain_depth_data_from_hirds.store_data_to_csv(site_id, path, idf)
        add_rain_depth_data_to_db(engine, site_id, path)


def rain_depths_to_db(engine, catchment_polygon: Polygon, path, idf: str):
    """Store rainfall data of all the sites within the catchment area in the database."""
    sites_id_in_catchment = get_sites_id_in_catchment(engine, catchment_polygon)
    # check if 'rainfall_depth' table is already in the database
    if check_table_exists(engine, "rainfall_depth"):
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
    # Set idf to "false" for rain depth data and to "true" for rain intensity data
    idf = "false"
    engine = setup_environment.get_database()
    catchment_polygon = hyetograph.catchment_area_geometry_info(catchment_file)
    rain_depths_to_db(engine, catchment_polygon, file_path_to_store, idf)


if __name__ == "__main__":
    main()
