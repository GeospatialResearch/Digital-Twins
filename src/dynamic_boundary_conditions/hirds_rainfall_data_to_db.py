# -*- coding: utf-8 -*-
"""
@Script name: hirds_rainfall_data_to_db.py
@Description: Store rainfall data of all the sites within the catchment area in the database.
@Author: pkh35
@Date: 20/01/2022
@Last modified by: sli229
@Last modified date: 6/10/2022
"""

import pandas as pd
import geopandas as gpd
import sqlalchemy
import pathlib
import logging
from typing import List
from shapely.geometry import Polygon
from src.digitaltwin import setup_environment
from src.dynamic_boundary_conditions import hyetograph
from src.dynamic_boundary_conditions import rainfall_data_from_hirds

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def db_rain_table_name(idf: bool) -> str:
    """
    Return the relevant rainfall data table name used in the database.

    Parameters
    ----------
    idf : bool
        Set to False for rainfall depth data, and True for rainfall intensity data.
    """
    table_name = "rainfall_depth" if idf is False else "rainfall_intensity"
    return table_name


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


def get_sites_id_not_in_db(engine, sites_id_in_catchment: List[str], idf: bool) -> List[str]:
    """
    Get the list of rainfall sites ids that are in the catchment area but are not in the database.

    Parameters
    ----------
    engine
        Engine used to connect to the database.
    sites_id_in_catchment : List[str]
        Rainfall sites ids within the catchment area.
    idf : bool
        Set to False for rainfall depth data, and True for rainfall intensity data.
    """
    rain_table_name = db_rain_table_name(idf)
    query = f"SELECT DISTINCT site_id FROM {rain_table_name};"
    # Get dataframe of sites in the database
    sites_id_in_db = pd.read_sql_query(query, engine)
    # Convert dataframe to list of sites in the database
    sites_id_in_db = sites_id_in_db["site_id"].tolist()
    # yields the elements in `sites_id_in_catchment` that are NOT in `sites_id_in_db`
    sites_id_not_in_db = list(set(sites_id_in_catchment).difference(sites_id_in_db))
    return sites_id_not_in_db


def add_rainfall_data_to_db(engine, site_id: str, idf: bool):
    """
    Store each site's rainfall data in the database.

    Parameters
    ----------
    engine
        Engine used to connect to the database.
    site_id : str
        HIRDS rainfall site id.
    idf : bool
        Set to False for rainfall depth data, and True for rainfall intensity data.
    """
    rain_table_name = db_rain_table_name(idf)
    site_data = rainfall_data_from_hirds.get_data_from_hirds(site_id, idf)
    layout_structure = rainfall_data_from_hirds.get_layout_structure_of_data(site_data)

    for (skip_rows, rcp, time_period, category) in layout_structure:
        rain_data = rainfall_data_from_hirds.convert_to_tabular_data(
            site_data, site_id, skip_rows, rcp, time_period, category)
        rain_data.to_sql(rain_table_name, engine, index=False, if_exists="append")
    log.info(f"Added {rain_table_name} data for site {site_id} to database")


def add_each_site_rainfall_data(engine, sites_id_list: List[str], idf: bool):
    """
    Loop through all the sites in the sites_id_list, and store each site's rainfall data in the database.

    Parameters
    ----------
    engine
        Engine used to connect to the database.
    sites_id_list : List[str]
        Rainfall sites' ids.
    idf : bool
        Set to False for rainfall depth data, and True for rainfall intensity data.
    """
    for site_id in sites_id_list:
        add_rainfall_data_to_db(engine, site_id, idf)


def rainfall_data_to_db(engine, catchment_polygon: Polygon, idf: bool):
    """
    Store rainfall data of all the sites within the catchment area in the database.

    Parameters
    ----------
    engine
        Engine used to connect to the database.
    catchment_polygon : Polygon
        Desired catchment area.
    idf : bool
        Set to False for rainfall depth data, and True for rainfall intensity data.
    """
    sites_id_in_catchment = get_sites_id_in_catchment(engine, catchment_polygon)
    rain_table_name = db_rain_table_name(idf)
    # check if 'rainfall_depth' or 'rainfall_intensity' table is already in the database
    if check_table_exists(engine, rain_table_name):
        sites_id_not_in_db = get_sites_id_not_in_db(engine, sites_id_in_catchment, idf)
        # Check if sites_id_not_in_db is not empty
        if sites_id_not_in_db:
            add_each_site_rainfall_data(engine, sites_id_not_in_db, idf)
        else:
            log.info(f"{rain_table_name} data for sites in the requested catchment already available in the database.")
    else:
        # check if sites_id_in_catchment is not empty
        if sites_id_in_catchment:
            add_each_site_rainfall_data(engine, sites_id_in_catchment, idf)
        else:
            log.info("There are no sites within the requested catchment area, select a wider area.")


def main():
    catchment_file = pathlib.Path(r"src\dynamic_boundary_conditions\catchment_polygon.shp")
    engine = setup_environment.get_database()
    catchment_polygon = hyetograph.catchment_area_geometry_info(catchment_file)
    # Set idf to False for rain depth data and to True for rain intensity data
    rainfall_data_to_db(engine, catchment_polygon, idf=False)
    rainfall_data_to_db(engine, catchment_polygon, idf=True)


if __name__ == "__main__":
    main()
