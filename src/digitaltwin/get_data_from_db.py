# -*- coding: utf-8 -*-
"""
@author: pkh35, sli229
"""

import pathlib
import json

import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon
from shapely.geometry import box
from sqlalchemy.engine import Engine

from src.digitaltwin import setup_environment
from src.digitaltwin import get_data_from_apis


def get_nz_boundary_polygon(engine: Engine, to_crs: int = 2193) -> Polygon:
    query = "SELECT * FROM region_geometry;"
    regional_council = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry")
    nz_boundary = regional_council.dissolve(aggfunc="sum").explode(index_parts=True).reset_index(level=0, drop=True)
    nz_boundary["geometry_area"] = nz_boundary["geometry"].area
    nz_boundary = nz_boundary.sort_values(by="geometry_area", ascending=False).head(1)
    nz_boundary = nz_boundary.to_crs(to_crs)
    nz_boundary_polygon = nz_boundary["geometry"][0]
    return nz_boundary_polygon


def get_nz_bounding_box(engine: Engine, to_crs: int = 2193, file_name: str = "nz_bbox.geojson") -> None:
    file_path = pathlib.Path.cwd() / file_name
    if not file_path.is_file():
        nz_boundary_polygon = get_nz_boundary_polygon(engine, to_crs)
        min_x, min_y, max_x, max_y = nz_boundary_polygon.bounds
        bbox = box(min_x, min_y, max_x, max_y)
        nz_bbox = gpd.GeoDataFrame(geometry=[bbox], crs=2193)
        nz_bbox.to_file(file_name, driver="GeoJSON")


def get_data_from_db(engine, geometry: gpd.GeoDataFrame, source_list: tuple):
    """Perform spatial query within the database for the requested polygon."""
    get_data_from_apis.get_data_from_apis(engine, geometry, source_list)
    user_geometry = geometry.iloc[0, 0]
    poly = "'{}'".format(user_geometry)
    for source in source_list:
        #  2193 is the code for the NZTM projection
        query = f'select * from "{source}" where ST_Intersects(geometry, ST_GeomFromText({poly}, 2193))'
        output_data = pd.read_sql_query(query, engine)
        output_data["geometry"] = gpd.GeoSeries.from_wkb(output_data["geometry"])
        output_data = gpd.GeoDataFrame(output_data, geometry="geometry")
        print(source)
        print(output_data)


def main(selected_polygon_gdf: gpd.GeoDataFrame):
    engine = setup_environment.get_database()
    # load in the instructions, get the source list and polygon from the user
    instructions_file_path = pathlib.Path().cwd() / pathlib.Path(
        "src/instructions_get_data_from_db.json"
    )
    with open(instructions_file_path, "r") as file_pointer:
        instructions = json.load(file_pointer)
    source_list = tuple(instructions["source_name"])

    get_data_from_db(engine, selected_polygon_gdf, source_list)


if __name__ == "__main__":
    sample_polygon = gpd.GeoDataFrame.from_file("selected_polygon.geojson")
    main(sample_polygon)
