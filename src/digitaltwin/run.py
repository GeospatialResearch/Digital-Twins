# -*- coding: utf-8 -*-
"""
Created on Mon Sep 13 15:21:34 2021

@author: pkh35
"""
import json
import pathlib

from src import config
from src.digitaltwin import setup_environment, insert_api_to_table, get_data_using_geoapis, get_data_from_db


def input_data(file):
    """Read json instruction file to store record i.e. api details to the database."""
    # load in the instructions to add building outlines api from LINZ
    file_path = pathlib.Path().cwd() / pathlib.Path(file)
    with open(file_path, "r") as file_pointer:
        instructions = json.load(file_pointer)
    instruction_node = instructions["instructions"]

    return instruction_node


def main():
    # Connect to the database
    engine = setup_environment.get_database()
    # Store regional council data in the database
    get_data_using_geoapis.store_regional_council_to_db(engine, layer_id=111182, clipped=False)
    # Store regional council data in the database
    get_data_using_geoapis.store_regional_council_to_db(engine, layer_id=111181, clipped=True)
    # Store sea-draining catchments data in the database
    get_data_using_geoapis.store_sea_drain_catchments_to_db(engine, layer_id=99776)
    
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
    main()
