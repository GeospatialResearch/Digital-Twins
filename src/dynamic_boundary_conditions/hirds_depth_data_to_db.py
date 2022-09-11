# -*- coding: utf-8 -*-
"""
Created on Thu Jan 20 15:09:11 2022

@author: pkh35
"""

import pandas as pd
import geopandas as gpd
import numpy as np
import sqlalchemy
import pathlib
from shapely.geometry import Polygon
from src.dynamic_boundary_conditions import rain_depth_data_from_hirds


def check_table_exists(db_table_name: str, engine) -> bool:
    """Check if table exists in the database."""
    insp = sqlalchemy.inspect(engine)
    return insp.has_table(db_table_name, schema="public")


def get_sites_id_in_catchment(catchment_polygon: Polygon, engine) -> list:
    """Get rainfall sites id within the catchment area from the 'rainfall_sites' table in the database."""
    query = f"""SELECT * FROM rainfall_sites AS rs
        WHERE ST_Intersects(rs.geometry, ST_GeomFromText('{catchment_polygon}', 4326))"""
    sites_in_catchment = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry", crs=4326)
    sites_id = sites_in_catchment["site_id"]
    sites_id_list = sites_id.tolist()
    return sites_id_list


def get_sites_not_in_db(engine, sites_in_catchment):
    """To only get the data for the sites for which data are not avialble in
    the database."""
    query = "SELECT DISTINCT site_id FROM rainfall_depth;"
    gauges = engine.execute(query)
    sites = gauges.fetchall()
    sites = list(sites)
    sites_in_db = []
    for i in range(len(sites)):
        sites_in_db.append(sites[i][0])
    # yields the elements in `sites_in_catchment` that are NOT in `sites_in_db`
    sites = np.setdiff1d(sites_in_catchment, sites_in_db)
    return sites


def get_data_from_csv(filename: str, site_id: str, rcp, time_period, n: int):
    """Read data of the diffrent time period and return a dataframe."""
    hirds_data = pd.read_csv(
        filename, skiprows=n, nrows=12, index_col=None, quotechar='"'
    )
    hirds_data["site_id"] = site_id
    hirds_data["rcp"] = rcp
    hirds_data["time_period"] = time_period
    hirds_data.columns = hirds_data.columns.str.lower()
    return hirds_data


def add_rain_depth_data_to_db(path: str, site_id: str, engine):
    """Store each site's depth data in the database. Each csv file contains
    data for historical rainfall depth, and for various rcp and time period.
    To view the csv file, go to : https://hirds.niwa.co.nz/, select a site and
    generate a report, there are rainfall depths for diffrent RCP Scenarios.
    To understand the structure of the CSV file, download the spreadsheet.
    """
    filename = pathlib.Path(f"{site_id}_rain_depth.csv")
    filepath = (path / filename)

    the_values = [
        (None, None, 12),
        (2.6, "2031-2050", 40),
        (2.6, "2081-2100", 54),
        (4.5, "2031-2050", 68),
        (4.5, "2081-2100", 82),
        (6, "2031-2050", 96),
        (6, "2081-2100", 110),
        (8.5, "2031-2050", 124),
        (8.5, "2081-2100", 138),
    ]

    print("Adding data for site", site_id, "to database")
    for (rcp, time_period, n) in the_values:
        site_data = get_data_from_csv(
            filepath, site_id, rcp=rcp, time_period=time_period, n=n
        )
        site_data.to_sql("rainfall_depth", engine, index=False, if_exists="append")


def rainfall_depths_to_db(engine, catchment_polygon: Polygon, path):
    """Store depth data of all the sites within the catchment area in the database."""
    sites_id_list = get_sites_id_in_catchment(catchment_polygon, engine)
    # check if 'rainfall_depth' table is already in the database
    if check_table_exists("rainfall_depth", engine):
        site_ids = get_sites_not_in_db(engine, sites_id_list)
        if site_ids.size:
            for site_id in site_ids:
                rain_depth_data_from_hirds.store_data_to_csv(site_id, path)
                add_rain_depth_data_to_db(path, site_id, engine)
        else:
            print("Sites for the requested catchment available in the database.")
    else:
        # check if sites_id_list is not empty
        if sites_id_list:
            for site_id in sites_id_list:
                rain_depth_data_from_hirds.store_data_to_csv(site_id, path)
                add_rain_depth_data_to_db(path, site_id, engine)
        else:
            print("There are no sites within the requested catchment area, select a wider area")


if __name__ == "__main__":
    from src.digitaltwin import setup_environment
    from src.dynamic_boundary_conditions import hyetograph

    catchment_file = pathlib.Path(
        r"C:\Users\sli229\Projects\Digital-Twins\src\dynamic_boundary_conditions\catchment_polygon.shp")
    file_path_to_store = pathlib.Path(r"U:\Research\FloodRiskResearch\DigitalTwin\hirds_rainfall_data")

    engine = setup_environment.get_database()
    catchment_polygon = hyetograph.catchment_area_geometry_info(catchment_file)
    rainfall_depths_to_db(engine, catchment_polygon, file_path_to_store)
