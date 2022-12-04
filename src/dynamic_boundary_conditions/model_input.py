# -*- coding: utf-8 -*-
"""
@Script name: model_input.py
@Description:
@Author: sli229
@Date: 1/12/2022
"""

import pathlib
import geopandas as gpd
from typing import List
from shapely.geometry import Polygon
from src.digitaltwin import setup_environment
from src.dynamic_boundary_conditions import main_rainfall, thiessen_polygons


def get_sites_id_in_catchment(sites_in_catchment: gpd.GeoDataFrame) -> List[str]:
    sites_id_in_catchment = sites_in_catchment["site_id"].tolist()
    return sites_id_in_catchment


def sites_coverage_intersect_catchment(
        sites_in_catchment: gpd.GeoDataFrame,
        catchment_polygon: Polygon) -> gpd.GeoDataFrame:
    catchment_area = gpd.GeoDataFrame(index=[0], crs='epsg:4326', geometry=[catchment_polygon])
    intersection_area = gpd.overlay(sites_in_catchment, catchment_area, how="intersection")
    return intersection_area


def sites_area_in_catchment(
        sites_in_catchment: gpd.GeoDataFrame,
        catchment_polygon: Polygon) -> gpd.GeoDataFrame:
    sites_area = sites_coverage_intersect_catchment(sites_in_catchment, catchment_polygon)
    sites_area['area_in_km2'] = sites_area.to_crs(3857).area / 1e6
    sites_area_total = sites_area['area_in_km2'].sum()
    sites_area_percent = sites_area['area_in_km2'] / sites_area_total
    sites_area.insert(3, "area_percent", sites_area_percent)
    return sites_area


def main():
    engine = setup_environment.get_database()
    catchment_file = pathlib.Path(r"src\dynamic_boundary_conditions\catchment_polygon.shp")
    catchment_polygon = main_rainfall.catchment_area_geometry_info(catchment_file)
    sites_in_catchment = thiessen_polygons.thiessen_polygons_from_db(engine, catchment_polygon)
    sites_area = sites_area_in_catchment(sites_in_catchment, catchment_polygon)
    print(sites_area)


if __name__ == "__main__":
    main()