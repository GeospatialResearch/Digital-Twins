# -*- coding: utf-8 -*-
"""
Created on Thu Jan 20 11:36:07 2022

@author: pkh35
"""

import pandas as pd
import geopandas as gpd
from geovoronoi import voronoi_regions_from_coords, points_to_coords
import sys
from src.digitaltwin import setup_environment
from src.dynamic_boundary_conditions import rainfall_sites


def thiessen_polygons(engine, catchment: gpd.GeoDataFrame, sites_in_catchment: gpd.GeoDataFrame):
    """Calculate the area covered by each site and store it in the database.
    catchment: get the geopandas dataframe of the catchment area.
    sites_in_catchment: get the geopandas dataframe of the sites in the catchment area.
    """
    if catchment.empty or sites_in_catchment.empty:
        print("No data available for the catchment or sites passed as an argument.")
        sys.exit()
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


def main():
    engine = setup_environment.get_database()
    nz_boundary = rainfall_sites.get_new_zealand_boundary(engine)
    sites_in_catchment = rainfall_sites.get_sites_locations(engine, nz_boundary)
    thiessen_polygons(engine, nz_boundary, sites_in_catchment)


if __name__ == "__main__":
    main()
