# -*- coding: utf-8 -*-
"""
Created on Mon Sep 13 15:21:34 2021

@author: pkh35
"""
import json
import os
import pathlib

from dotenv import load_dotenv

from digitaltwin import insert_api_to_table

load_dotenv()
Stats_NZ_KEY = os.getenv('KEY')


def input_data(file):
    """Read json instruction file to store record i.e. api details to the database."""
    # load in the instructions to add building outlines api from LINZ
    file_path = pathlib.Path().cwd() / pathlib.Path(file)
    with open(file_path, 'r') as file_pointer:
        instructions = json.load(file_pointer)
    instruction_node = instructions['instructions']
    source = instruction_node['source_name']
    region = instruction_node['region_name']
    geometry_column = instruction_node['geometry_col_name']
    url = instruction_node['url']
    api = instruction_node['api']
    data_provider = instruction_node['data_provider']
    layer = instruction_node['layer']
    record = {
        "source": source,
        "api": api,
        "url": url,
        "region": region,
        "layer": layer,
        "data_provider": data_provider,
        "geometry_column": geometry_column
    }
    return record


if __name__ == "__main__":
    record = input_data("instructions_linz.json")

    # call the function to insert record in apilinks table
    insert_api_to_table.insert_records(record['data_provider'],
                                       record['source'],
                                       record['api'], record['region'],
                                       record['geometry_column'],
                                       record['url'],
                                       record['layer'], Stats_NZ_KEY)
