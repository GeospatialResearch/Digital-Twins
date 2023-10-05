# -*- coding: utf-8 -*-
"""
This script runs each module in the Digital Twin using a Sample Polygon.
"""

from types import ModuleType
from typing import Dict

import geopandas as gpd
from newzealidar import datasets, process

from src.digitaltwin import run
from src.digitaltwin.utils import LogLevel
from src.dynamic_boundary_conditions.rainfall import main_rainfall
from src.dynamic_boundary_conditions.river import main_river
from src.dynamic_boundary_conditions.tide import main_tide_slr
from src.flood_model import bg_flood_model


def main(selected_polygon_gdf: gpd.GeoDataFrame, modules_with_log_levels: Dict[ModuleType, LogLevel]) -> None:
    """
    Runs each module in the Digital Twin using the selected polygon, i.e., the catchment area.

    Parameters
    ----------
    selected_polygon_gdf : gpd.GeoDataFrame
        A GeoDataFrame representing the selected polygon, i.e., the catchment area.
    modules_with_log_levels: Dict[ModuleType, LogLevel]
        The log level to set for each module's root logger.
        The available logging levels and their corresponding numeric values are:
        - LogLevel.CRITICAL (50)
        - LogLevel.ERROR (40)
        - LogLevel.WARNING (30)
        - LogLevel.INFO (20)
        - LogLevel.DEBUG (10)
        - LogLevel.NOTSET (0)

    Returns
    -------
    None
        This function does not return any value.
    """
    for module, log_level in modules_with_log_levels.items():
        module.main(selected_polygon_gdf, log_level=log_level)


if __name__ == '__main__':
    # Define a dictionary mapping each module to its log level
    module_to_log_level = {
        run: LogLevel.DEBUG,
        # datasets: LogLevel.DEBUG,  # only need to run it one time to initiate db.dataset table
        process: LogLevel.DEBUG,
        main_rainfall: LogLevel.DEBUG,
        main_tide_slr: LogLevel.DEBUG,
        main_river: LogLevel.DEBUG,
        bg_flood_model: LogLevel.DEBUG,
    }

    sample_polygon = gpd.GeoDataFrame.from_file("selected_polygon.geojson")
    main(
        selected_polygon_gdf=sample_polygon,
        modules_with_log_levels=module_to_log_level
    )
