# -*- coding: utf-8 -*-
"""
@Description: This script executes the Digital Twin application.
@Author: sli229
"""

from typing import Dict
from types import ModuleType

import geopandas as gpd

from src.digitaltwin.utils import LogLevel
from src.digitaltwin import run
from src.lidar import lidar_metadata_in_db, dem_metadata_in_db
from src.dynamic_boundary_conditions import main_rainfall, main_tide_slr, main_river
from src.flood_model import bg_flood_model
import sys
sys.path.insert(0, r'../NewZeaLiDAR')
from newzealidar import datasets, process


def main(selected_polygon_gdf: gpd.GeoDataFrame, modules_with_log_levels: Dict[ModuleType, LogLevel]) -> None:
    for module, log_level in modules_with_log_levels.items():
        module.main(selected_polygon_gdf, log_level=log_level)


if __name__ == '__main__':
    # Define a dictionary mapping each module to its log level
    module_to_log_level = {
        run: LogLevel.DEBUG,
        datasets: LogLevel.DEBUG,  # only need to run it one time to initiate db.dataset table
        process: LogLevel.DEBUG,
        main_rainfall: LogLevel.DEBUG,
        main_tide_slr: LogLevel.DEBUG,
        main_river: LogLevel.DEBUG,
        bg_flood_model: LogLevel.DEBUG,
    }

    sample_polygon = gpd.GeoDataFrame.from_file("selected_polygon.geojson")
    main(sample_polygon, module_to_log_level)
