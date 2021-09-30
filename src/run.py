# -*- coding: utf-8 -*-
"""
Created on Mon Sep 13 15:21:34 2021

@author: pkh35
"""
import json
import pathlib

from src.digitaltwin import insert_api_to_table


def get_instructions(file_path):
    """load in the instructions to add building outlines api from LINZ"""
    with open(file_path, 'r') as file_pointer:
        instructions = json.load(file_pointer)
    return instructions


def insert_records_from_instructions(instructions):
    source = instructions['instructions']['source_name']
    region = instructions['instructions']['region_name']
    geometry_column = instructions['instructions']['geometry_col_name']
    url = instructions['instructions']['url']
    api = instructions['instructions']['api']
    data_provider = instructions['instructions']['data_provider']
    layer = instructions['instructions']['layer']
    # get stats NZ key from:
    # https://datafinder.stats.govt.nz/layer/105133-regional-council-2021-generalised/webservices/
    Stats_NZ_KEY = 'YOUR_KEY'

    # call the function to insert record in apilinks table
    insert_api_to_table.insert_records(data_provider, source, api, region,
                                       geometry_column, url, layer, Stats_NZ_KEY)


def main():
    file_path = pathlib.Path().cwd() / pathlib.Path("digitaltwin/instructions_statsnz.json")
    instructions = get_instructions(file_path)
    insert_records_from_instructions(instructions)


if __name__ == "__main__":
    main()
