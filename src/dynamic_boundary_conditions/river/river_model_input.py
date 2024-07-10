# -*- coding: utf-8 -*-
"""This script handles the task of generating the requested river model inputs for BG-Flood."""

import logging
import pathlib

import geopandas as gpd

from src.dynamic_boundary_conditions.river import main_river

log = logging.getLogger(__name__)


def generate_river_model_input(bg_flood_dir: pathlib.Path, hydrograph_data: gpd.GeoDataFrame) -> None:
    """
    Generate the requested river model inputs for BG-Flood.

    Parameters
    ----------
    bg_flood_dir : pathlib.Path
        The BG-Flood model directory.
    hydrograph_data : gpd.GeoDataFrame
        A GeoDataFrame containing hydrograph data for the requested REC river inflow scenario.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Remove any existing river model inputs in the BG-Flood directory
    main_river.remove_existing_river_inputs(bg_flood_dir)
    # Log that the generation of river model inputs has started
    log.info("Generating the river model inputs for BG-Flood.")
    # Group the hydrograph data based on specific attributes
    grouped = hydrograph_data.groupby(
        by=["river_input_point_no", hydrograph_data["river_input_point"].to_wkt(), "dem_resolution", "areakm2"],
        sort=False)
    # Iterate through each group of hydrograph data
    for group_name, group_data in grouped:
        # Unpack group_name tuple to extract 'river_input_point_no' and 'dem_resolution'
        river_input_point_no, _, dem_resolution, _ = group_name
        # Create a buffer around the 'river_input_point' to define the 'river_input_cell'
        group_data["river_input_cell"] = group_data["river_input_point"].buffer(distance=dem_resolution/2, cap_style=3)
        # Retrieve the unique 'river_input_cell' geometry
        river_input_cell = group_data["river_input_cell"].unique()[0]
        # Extract bounding box coordinates (x_min, y_min, x_max, y_max) of the 'river_input_cell'
        x_min, y_min, x_max, y_max = river_input_cell.bounds
        # Extract relevant columns for the river model input data
        river_model_input_data = group_data[["seconds", "flow"]].reset_index(drop=True)
        # Generate a file path based on the 'river_input_point_no' and cell bounds
        file_path = bg_flood_dir / f"river{river_input_point_no}_{x_min}_{x_max}_{y_min}_{y_max}.txt"
        # Save the river model input data as a text file
        river_model_input_data.to_csv(file_path, index=False, header=False)
    # Log a message indicating the successful generation of the river model inputs
    log.info("Successfully generated the river model inputs for BG-Flood.")
