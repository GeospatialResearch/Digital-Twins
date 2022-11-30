# -*- coding: utf-8 -*-
"""
@Script name: thiessen_polygon_calculator.py
@Description: Calculate the area covered by each rainfall site and store it in the database.
@Author: pkh35
@Date: 20/01/2022
@Last modified by: sli229
@Last modified date: 28/09/2022
"""

import pandas as pd
import geopandas as gpd
from geovoronoi import voronoi_regions_from_coords, points_to_coords
import logging
import sys
from shapely.geometry import Polygon
from src.digitaltwin import setup_environment
from src.dynamic_boundary_conditions import rainfall_sites
from src.dynamic_boundary_conditions import hirds_rainfall_data_to_db

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def thiessen_polygons_calculator(area_of_interest: Polygon, sites_within_aoi: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Create thiessen polygons and calculate the area covered by each rainfall site within the area of interest.

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
            site_voronoi = site_voronoi[["site_id", "site_name", "area_in_km2", "geometry"]]
            rainfall_sites_coverage = gpd.GeoDataFrame(
                pd.concat([rainfall_sites_coverage, site_voronoi], ignore_index=True))
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


def main():
    engine = setup_environment.get_database()
    nz_boundary_polygon = rainfall_sites.get_new_zealand_boundary(engine)
    sites_within_aoi = rainfall_sites.get_sites_locations(engine, nz_boundary_polygon)
    thiessen_polygons_to_db(engine, nz_boundary_polygon, sites_within_aoi)


if __name__ == "__main__":
    main()
