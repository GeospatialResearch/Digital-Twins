# -*- coding: utf-8 -*-
"""
@Description: Generate the requested river model inputs for BG-Flood.
@Author: sli229
"""

import logging
import pathlib

import geopandas as gpd

from src.dynamic_boundary_conditions import main_river

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def generate_river_model_input(bg_flood_dir: pathlib.Path, hydrograph_data: gpd.GeoDataFrame) -> None:
    """
    Generate the requested river model inputs for BG-Flood.

    Parameters
    ----------
    bg_flood_dir : pathlib.Path
        The BG-Flood model directory.
    hydrograph_data : pd.DataFrame
        A GeoDataFrame containing the hydrograph data for the requested river flow scenario.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Remove any existing river model inputs in the BG-Flood directory
    main_river.remove_existing_river_inputs(bg_flood_dir)
    # Group the hydrograph data based on specific attributes
    grouped = hydrograph_data.groupby(['target_point_no', hydrograph_data['target_point'].to_wkt(),
                                       'dem_resolution', 'areakm2'], sort=False)
    # Iterate through each group of hydrograph data
    for group_name, group_data in grouped:
        # Unpack group_name tuple to extract target_point_no and dem_resolution
        target_point_no, _, dem_resolution, _ = group_name
        # Create a buffer around the target point to define the target cell
        group_data['target_cell'] = group_data['target_point'].buffer(distance=dem_resolution / 2, cap_style=3)
        # Retrieve the unique target_cell geometry
        target_cell = group_data['target_cell'].unique()[0]
        # Extract bounding box coordinates (x_min, y_min, x_max, y_max) of the target_cell
        x_min, y_min, x_max, y_max = target_cell.bounds
        # Extract relevant columns for the river model input
        model_input_data = group_data[['seconds', 'flow']].reset_index(drop=True)
        # Generate a file path based on the target point and cell bounds
        file_path = bg_flood_dir / f"river{target_point_no}_{x_min}_{x_max}_{y_min}_{y_max}.txt"
        # Save the river model input as a text file
        model_input_data.to_csv(file_path, index=False, header=False)
    # Log a message indicating the successful generation of the river model inputs
    log.info(f"Successfully generated the river model inputs for BG-Flood. Located in: {bg_flood_dir}")
