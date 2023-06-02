# -*- coding: utf-8 -*-
"""
@Description: Calculate the area covered by each rainfall site across New Zealand and store it in the database,
              then get all rainfall sites voronoi (thiessen polygons) areas that are within the catchment area.
@Author: pkh35, sli229
"""

import logging

import geopandas as gpd
import pandas as pd
from geovoronoi import voronoi_regions_from_coords, points_to_coords
from shapely.geometry import Polygon

from src.digitaltwin import setup_environment
from src.dynamic_boundary_conditions import main_rainfall, hirds_rainfall_data_to_db

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def get_new_zealand_boundary(engine) -> Polygon:
    """
    Get the boundary geometry of New Zealand from the 'region_geometry' table in the database.

    Parameters
    ----------
    engine
        Engine used to connect to the database.
    """
    query = "SELECT geometry FROM region_geometry WHERE regc2021_v1_00_name='New Zealand'"
    nz_boundary = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry", crs=2193)
    nz_boundary = nz_boundary.to_crs(4326)
    nz_boundary_polygon = nz_boundary["geometry"][0]
    return nz_boundary_polygon


def get_sites_within_aoi(engine, area_of_interest: Polygon) -> gpd.GeoDataFrame:
    """
    Get all rainfall sites within the catchment area from the database and return the required data in
    GeoDataFrame format.

    Parameters
    ----------
    engine
        Engine used to connect to the database.
    area_of_interest : Polygon
        Area of interest polygon.
    """
    # Get all rainfall sites within the area of interest from the database
    query = f"SELECT * FROM rainfall_sites AS rs " \
            f"WHERE ST_Within(rs.geometry, ST_GeomFromText('{area_of_interest}', 4326))"
    sites_in_aoi = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry", crs=4326)
    # Reset the index
    sites_in_aoi.reset_index(drop=True, inplace=True)
    return sites_in_aoi


def thiessen_polygons_calculator(area_of_interest: Polygon, sites_in_aoi: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Create thiessen polygons for all rainfall sites within the area of interest (e.g. New Zealand Boundary) and
    calculate the area covered by each rainfall site.

    Parameters
    ----------
    area_of_interest : Polygon
        Area of interest polygon.
    sites_in_aoi : gpd.GeoDataFrame
        Rainfall sites within the area of interest.
    """
    if area_of_interest.is_empty:
        raise ValueError("No data available for area_of_interest passed as argument")
    if sites_in_aoi.empty:
        raise ValueError("No data available for sites_in_aoi passed as argument")
    coordinates = points_to_coords(sites_in_aoi["geometry"])
    region_polys, region_pts = voronoi_regions_from_coords(coordinates, area_of_interest, per_geom=False)
    voronoi_regions = list(region_polys.values())
    sites_in_voronoi_order = pd.DataFrame()
    for site_index in region_pts.values():
        site_index = site_index[0]
        site = sites_in_aoi.filter(items=[site_index], axis=0)
        sites_in_voronoi_order = pd.concat([sites_in_voronoi_order, site])
    rainfall_sites_voronoi = gpd.GeoDataFrame(sites_in_voronoi_order, geometry=voronoi_regions, crs="epsg:4326")
    rainfall_sites_voronoi["area_in_km2"] = rainfall_sites_voronoi.to_crs(3857).area / 1e6
    rainfall_sites_voronoi = rainfall_sites_voronoi[["site_id", "site_name", "area_in_km2", "geometry"]]
    return rainfall_sites_voronoi


def thiessen_polygons_to_db(engine, area_of_interest: Polygon, sites_in_aoi: gpd.GeoDataFrame):
    """
    Store thiessen polygon outputs (i.e. rainfall sites coverages) to the database。

    Parameters
    ----------
    engine
        Engine used to connect to the database.
    area_of_interest : Polygon
        Area of interest polygon.
    sites_in_aoi : gpd.GeoDataFrame
        Rainfall sites within the area of interest.
    """
    if hirds_rainfall_data_to_db.check_table_exists(engine, "rainfall_sites_voronoi"):
        log.info("Rainfall sites coverage data already exists in the database.")
    else:
        rainfall_sites_voronoi = thiessen_polygons_calculator(area_of_interest, sites_in_aoi)
        rainfall_sites_voronoi.to_postgis("rainfall_sites_voronoi", engine, if_exists="replace")
        log.info("Stored rainfall sites voronoi (thiessen polygons) data in the database.")


def thiessen_polygons_from_db(engine, catchment_polygon: Polygon):
    """
    Get all rainfall sites coverage areas (thiessen polygons) that intersects or are within the catchment area.

    Parameters
    ----------
    engine
        Engine used to connect to the database.
    catchment_polygon : Polygon
        Desired catchment area.
    """
    query = f"SELECT * FROM rainfall_sites_voronoi AS rsv " \
            f"WHERE ST_Intersects(rsv.geometry, ST_GeomFromText('{catchment_polygon}', 4326))"
    sites_in_catchment = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry", crs=4326)
    # Reset the index
    sites_in_catchment.reset_index(drop=True, inplace=True)
    return sites_in_catchment
