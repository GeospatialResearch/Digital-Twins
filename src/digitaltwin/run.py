# -*- coding: utf-8 -*-
"""
Created on Mon Sep 13 15:21:34 2021

@author: pkh35
"""
import pathlib
import json

import geopandas as gpd

from src import config
from src.digitaltwin import setup_environment, insert_api_to_table, store_data_to_db, get_data_from_db


def input_data(file):
    """Read json instruction file to store record i.e. api details to the database."""
    # load in the instructions to add building outlines api from LINZ
    file_path = pathlib.Path().cwd() / pathlib.Path(file)
    with open(file_path, "r") as file_pointer:
        instructions = json.load(file_pointer)
    instruction_node = instructions["instructions"]

    return instruction_node


def main(selected_polygon_gdf: gpd.GeoDataFrame) -> None:
    # Connect to the database
    engine = setup_environment.get_database()
    # Store data in the database
    store_data_to_db.store_regional_council_to_db(engine, layer_id=111182, clipped=False)
    store_data_to_db.store_regional_council_to_db(engine, layer_id=111181, clipped=True)
    store_data_to_db.store_sea_drain_catchments_to_db(engine, layer_id=99776)
    store_data_to_db.store_nz_roads_to_db(engine, layer_id=53382, bounding_polygon=selected_polygon_gdf)
    store_data_to_db.store_nz_building_outlines_to_db(engine, layer_id=101292, bounding_polygon=selected_polygon_gdf)
    # Write nz bounding box out to file
    get_data_from_db.get_nz_bounding_box_to_file(engine)

    record = input_data("src/digitaltwin/instructions_run.json")
    # Substitute api key into link template
    linz_api_key = config.get_env_variable("LINZ_API_KEY")
    record["api"] = record["api"].format(api_key=linz_api_key)

    # Call the function to insert record in apilinks table
    insert_api_to_table.insert_records(
        engine=engine,
        data_provider=record["data_provider"],
        source_name=record["source_name"],
        api=record["api"],
        region_name=record["region_name"],
        geometry_col_name=record["geometry_col_name"],
        url=record["url"],
        layer=record["layer"],
    )


if __name__ == "__main__":
    sample_polygon = gpd.GeoDataFrame.from_file("selected_polygon.geojson")
    main(sample_polygon)
