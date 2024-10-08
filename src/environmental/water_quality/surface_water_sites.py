# -*- coding: utf-8 -*-
"""
Fetch surface water site data from ECAN using the ArcGIS REST API, store it in the database, and
retrieve it for the requested area of interest.
"""

import logging

import geopandas as gpd
from sqlalchemy.engine import Engine
from sqlalchemy.sql import text

from src.digitaltwin.arcgis_rest_api import fetch_arcgis_rest_api_data
from src.digitaltwin.tables import check_table_exists

log = logging.getLogger(__name__)


def store_surface_water_sites_to_db(
        engine: Engine,
        area_of_interest: gpd.GeoDataFrame = None,
        output_sr: int = None) -> None:
    """
    Fetch surface water site data from ECAN using the ArcGIS REST API and store it in the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    area_of_interest : gpd.GeoDataFrame = None
        A GeoDataFrame representing the area of interest for data retrieval. If not provided, all data will be fetched.
    output_sr : int = None
        The EPSG code of the spatial reference system in which the requested data should be returned if no area of
        interest is provided.
    """
    # Define the table name for storing the surface water site data
    table_name = "surface_water_sites"
    # Check if the table already exists in the database
    if check_table_exists(engine, table_name):
        log.info(f"'{table_name}' already exists in the database.")
    else:
        # The URL for retrieving surface water site data from ECAN
        surface_url = "https://gis.ecan.govt.nz/arcgis/rest/services/Public/WaterQualityandMonitoring/MapServer/0"
        # Fetch surface water site data for the area of interest using the ArcGIS REST API
        surface_sites = fetch_arcgis_rest_api_data(surface_url, area_of_interest, output_sr)
        # Store the surface water site data in the relevant table in the database
        log.info(f"Adding '{table_name}' to the database.")
        surface_sites.to_postgis(table_name, engine, index=False, if_exists="replace")
        log.info(f"Successfully added '{table_name}' to the database.")


def get_surface_water_sites_from_db(engine: Engine, catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Retrieve surface water site data from the database for the specified catchment area.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the retrieved surface water site data for the requested catchment area.
    """
    # Extract the geometry of the catchment area and its corresponding CRS
    catchment_polygon = catchment_area["geometry"][0]
    catchment_crs = catchment_area.crs.to_epsg()
    # Query to retrieve surface water sites that intersect with the catchment polygon
    command_text = """
        SELECT *
        FROM surface_water_sites AS sws
        WHERE ST_Intersects(sws.geometry, ST_GeomFromText(:catchment_polygon, :catchment_crs));
        """
    query = text(command_text).bindparams(
        catchment_polygon=str(catchment_polygon),
        catchment_crs=str(catchment_crs)
    )
    # Execute the query and create a GeoDataFrame from the result
    sws_data = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry")
    return sws_data
