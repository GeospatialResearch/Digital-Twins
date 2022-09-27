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
from src.digitaltwin import setup_environment
from src.dynamic_boundary_conditions import rainfall_sites
from src.dynamic_boundary_conditions import hirds_rainfall_data_to_db

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def thiessen_polygons(engine, catchment: gpd.GeoDataFrame, sites_in_catchment: gpd.GeoDataFrame):
    """
    Calculate the area covered by each rainfall site and store it in the database.

    Parameters
    ----------
    engine
        Engine used to connect to the database.
    catchment : gpd.GeoDataFrame
        New Zealand catchment boundary geometry.
    sites_in_catchment : gpd.GeoDataFrame
        Rainfall sites within the catchment area.
    """
    if catchment.empty or sites_in_catchment.empty:
        log.info("No data available for the catchment or sites_in_catchment passed as arguments.")
        sys.exit()
    elif hirds_rainfall_data_to_db.check_table_exists(engine, "rainfall_sites_coverage"):
        log.info("Rainfall sites coverage data already exists in the database.")
    else:
        catchment_area = catchment["geom"][0]
        coords = points_to_coords(sites_in_catchment["geometry"])
        region_polys, region_pts = voronoi_regions_from_coords(coords, catchment_area, per_geom=False)

        rainfall_sites_coverage = gpd.GeoDataFrame()
        for key, value in region_pts.items():
            value = value[0]
            site = sites_in_catchment.filter(items=[value], axis=0)
            site.reset_index(inplace=True)
            site.drop(columns=["index", "geometry"], inplace=True)
            voronoi = gpd.GeoDataFrame(crs="epsg:4326", geometry=[region_polys[key]])
            voronoi["area_in_km2"] = voronoi.to_crs(3857).area / 1e6
            site_voronoi = pd.concat([site, voronoi], axis=1)
            site_voronoi = site_voronoi[["site_id", "area_in_km2", "geometry"]]
            rainfall_sites_coverage = pd.concat([rainfall_sites_coverage, site_voronoi], ignore_index=True)
        rainfall_sites_coverage.to_postgis("rainfall_sites_coverage", engine, if_exists="replace")
        log.info("Stored rainfall sites coverage data in the database.")


def main():
    engine = setup_environment.get_database()
    nz_boundary = rainfall_sites.get_new_zealand_boundary(engine)
    sites_in_catchment = rainfall_sites.get_sites_locations(engine, nz_boundary)
    thiessen_polygons(engine, nz_boundary, sites_in_catchment)


if __name__ == "__main__":
    main()
