# -*- coding: utf-8 -*-
"""
@Description: Calculate the area covered by each rainfall site throughout New Zealand and store it in the database.
              Retrieve the coverage areas (Thiessen polygons) for all rainfall sites located within the catchment area.
@Author: pkh35, sli229
"""

import logging

import geopandas as gpd
import pandas as pd
from geovoronoi import voronoi_regions_from_coords, points_to_coords
from shapely.geometry import Polygon
from sqlalchemy.engine import Engine

from src.digitaltwin import tables

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def get_sites_within_aoi(engine: Engine, area_of_interest: Polygon) -> gpd.GeoDataFrame:
    """
    Get all rainfall sites within the area of interest from the database and return the required data as a
    GeoDataFrame.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    area_of_interest : Polygon
        The polygon representing the area of interest.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the rainfall sites within the area of interest.
    """
    # Construct the query to fetch rainfall sites within the area of interest
    query = f"SELECT * FROM rainfall_sites AS rs " \
            f"WHERE ST_Within(rs.geometry, ST_GeomFromText('{area_of_interest}', 4326))"
    # Execute the query and retrieve the results as a GeoDataFrame
    sites_in_aoi = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry", crs=4326)
    # Reset the index
    sites_in_aoi.reset_index(drop=True, inplace=True)
    return sites_in_aoi


def thiessen_polygons_calculator(area_of_interest: Polygon, sites_in_aoi: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Create Thiessen polygons for rainfall sites within the area of interest and calculate the area covered by each
    rainfall site.

    Parameters
    ----------
    area_of_interest : Polygon
        The polygon representing the area of interest.
    sites_in_aoi : gpd.GeoDataFrame
        Rainfall sites within the area of interest.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the Thiessen polygons, site information, and area covered by each rainfall site.

    Raises
    ------
    ValueError
        - If the provided 'area_of_interest' polygon is empty.
        - If the provided 'sites_in_aoi' GeoDataFrame does not contain any data.
    """
    # Check if the area of interest is empty
    if area_of_interest.is_empty:
        raise ValueError("No data available for 'area_of_interest' passed as argument.")
    # Check if the rainfall sites GeoDataFrame is empty
    if sites_in_aoi.empty:
        raise ValueError("No data available for 'sites_in_aoi' passed as argument.")
    # Convert the rainfall site coordinates to an array of coordinates
    coordinates = points_to_coords(sites_in_aoi["geometry"])
    # Generate Voronoi regions from the coordinates within the area of interest
    region_polys, region_pts = voronoi_regions_from_coords(coordinates, area_of_interest, per_geom=False)
    voronoi_regions = list(region_polys.values())
    sites_in_voronoi_order = pd.DataFrame()
    for site_index in region_pts.values():
        site_index = site_index[0]
        site = sites_in_aoi.filter(items=[site_index], axis=0)
        sites_in_voronoi_order = pd.concat([sites_in_voronoi_order, site])
    # Create a GeoDataFrame with Thiessen polygons, site information, and area covered by each rainfall site
    rainfall_sites_voronoi = gpd.GeoDataFrame(sites_in_voronoi_order, geometry=voronoi_regions, crs=4326)
    rainfall_sites_voronoi["area_in_km2"] = rainfall_sites_voronoi.to_crs(3857).area / 1e6
    rainfall_sites_voronoi = rainfall_sites_voronoi[["site_id", "site_name", "area_in_km2", "geometry"]]
    return rainfall_sites_voronoi


def thiessen_polygons_to_db(engine: Engine, area_of_interest: Polygon, sites_in_aoi: gpd.GeoDataFrame) -> None:
    """
    Store the data representing the Thiessen polygons, site information, and the area covered by
    each rainfall site in the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    area_of_interest : Polygon
        The polygon representing the area of interest.
    sites_in_aoi : gpd.GeoDataFrame
        Rainfall sites within the area of interest.

    Returns
    -------
    None
        This function does not return any value.
    """
    table_name = "rainfall_sites_voronoi"
    # Check if the table already exists in the database
    if tables.check_table_exists(engine, table_name):
        log.info(f"Table '{table_name}' already exists in the database.")
    else:
        # Calculate the Thiessen polygons, i.e. the area covered by each rainfall site
        rainfall_sites_voronoi = thiessen_polygons_calculator(area_of_interest, sites_in_aoi)
        # Store the Thiessen polygons data in the database
        rainfall_sites_voronoi.to_postgis(f"{table_name}", engine, if_exists="replace")
        log.info(f"Stored '{table_name}' data in the database.")


def thiessen_polygons_from_db(engine: Engine, catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Get the coverage areas (Thiessen polygons) of all rainfall sites that intersect or are within the
    specified catchment area.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    catchment_area : gpd.GeoDataFrame
        A GeoDataFrame representing the catchment area.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame containing the coverage areas (Thiessen polygons) of rainfall sites within the catchment area.
    """
    # Extract the geometry of the catchment area
    catchment_polygon = catchment_area["geometry"].iloc[0]
    # Construct the query to get coverage areas (Thiessen polygons) of rainfall sites within the catchment area
    query = f"""
    SELECT *
    FROM rainfall_sites_voronoi AS rsv
    WHERE ST_Intersects(rsv.geometry, ST_GeomFromText('{catchment_polygon}', 4326))"""
    # Retrieve the data from the database
    sites_in_catchment = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry", crs=4326)
    # Reset the index
    sites_in_catchment.reset_index(drop=True, inplace=True)
    return sites_in_catchment
