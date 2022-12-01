# -*- coding: utf-8 -*-
"""
@Script name: thiessen_polygon_calculator.py
@Description: Calculate the area covered by each rainfall site and store it in the database.
@Author: pkh35
@Date: 20/01/2022
@Last modified by: sli229
@Last modified date: 1/12/2022
"""

import pathlib
import pandas as pd
import geopandas as gpd
from geovoronoi import voronoi_regions_from_coords, points_to_coords
import logging
import sys
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


def thiessen_polygons_calculator(area_of_interest: Polygon, sites_within_aoi: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Create thiessen polygons for all rainfall sites within the area of interest (e.g. New Zealand Boundary) and
    calculate the area covered by each rainfall site.

    Parameters
    ----------
    area_of_interest : Polygon
        Area of interest polygon.
    sites_within_aoi : gpd.GeoDataFrame
        Rainfall sites within the area of interest.
    """
    if area_of_interest.is_empty or sites_within_aoi.empty:
        log.info("No data available for area_of_interest or sites_within_aoi passed as arguments "
                 "to the 'thiessen_polygons' function")
        sys.exit()
    else:
        coords = points_to_coords(sites_within_aoi["geometry"])
        region_polys, region_pts = voronoi_regions_from_coords(coords, area_of_interest, per_geom=False)
        rainfall_sites_coverage = gpd.GeoDataFrame()
        for voronoi_region_id, sites_within_aoi_index in region_pts.items():
            sites_within_aoi_index = sites_within_aoi_index[0]
            site = sites_within_aoi.filter(items=[sites_within_aoi_index], axis=0)
            site = site.reset_index(drop=True).drop(columns=["geometry"])
            voronoi = gpd.GeoDataFrame(crs="epsg:4326", geometry=[region_polys[voronoi_region_id]])
            voronoi = voronoi.assign(area_in_km2=voronoi.to_crs(3857).area / 1e6)
            site_voronoi = pd.concat([site, voronoi], axis=1)
            site_voronoi = gpd.GeoDataFrame(site_voronoi[["site_id", "site_name", "area_in_km2", "geometry"]])
            rainfall_sites_coverage = pd.concat([rainfall_sites_coverage, site_voronoi], ignore_index=True)
        return rainfall_sites_coverage


def thiessen_polygons_to_db(engine, area_of_interest: Polygon, sites_within_aoi: gpd.GeoDataFrame):
    """
    Store thiessen polygon outputs (i.e. rainfall sites coverage) to the database。

    Parameters
    ----------
    engine
        Engine used to connect to the database.
    area_of_interest : Polygon
        Area of interest polygon.
    sites_within_aoi : gpd.GeoDataFrame
        Rainfall sites within the area of interest.
    """
    if hirds_rainfall_data_to_db.check_table_exists(engine, "rainfall_sites_coverage"):
        log.info("Rainfall sites coverage data already exists in the database.")
    else:
        rainfall_sites_coverage = thiessen_polygons_calculator(area_of_interest, sites_within_aoi)
        rainfall_sites_coverage.to_postgis("rainfall_sites_coverage", engine, if_exists="replace")
        log.info("Stored rainfall sites coverage data in the database.")


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
    query = f"SELECT * FROM rainfall_sites_coverage AS rsc " \
            f"WHERE ST_Intersects(rsc.geometry, ST_GeomFromText('{catchment_polygon}', 4326))"
    sites_in_catchment = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry", crs=4326)
    # Reset the index
    sites_in_catchment.reset_index(drop=True, inplace=True)
    return sites_in_catchment


def main():
    engine = setup_environment.get_database()
    nz_boundary_polygon = get_new_zealand_boundary(engine)
    sites_in_nz = get_sites_within_aoi(engine, nz_boundary_polygon)
    thiessen_polygons_to_db(engine, nz_boundary_polygon, sites_in_nz)

    catchment_file = pathlib.Path(r"src\dynamic_boundary_conditions\catchment_polygon.shp")
    catchment_polygon = main_rainfall.catchment_area_geometry_info(catchment_file)
    sites_in_catchment = thiessen_polygons_from_db(engine, catchment_polygon)
    print(sites_in_catchment)


if __name__ == "__main__":
    main()
