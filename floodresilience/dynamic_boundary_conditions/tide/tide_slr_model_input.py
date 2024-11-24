# -*- coding: utf-8 -*-
"""Generates the requested water level uniform boundary model input for BG-Flood."""

import logging
import pathlib

import pandas as pd

log = logging.getLogger(__name__)


def remove_existing_boundary_inputs(bg_flood_dir: pathlib.Path) -> None:
    """
    Remove existing uniform boundary input files from the specified directory.

    Parameters
    ----------
    bg_flood_dir : pathlib.Path
        BG-Flood model directory containing the uniform boundary input files.
    """
    # Iterate through all boundary files in the directory
    for boundary_file in bg_flood_dir.glob('*_bnd.txt'):
        # Remove the file
        boundary_file.unlink()


def generate_uniform_boundary_input(bg_flood_dir: pathlib.Path, tide_slr_data: pd.DataFrame) -> None:
    """
    Generate the requested water level uniform boundary model input for BG-Flood.

    Parameters
    ----------
    bg_flood_dir : pathlib.Path
        The BG-Flood model directory.
    tide_slr_data : pd.DataFrame
        A DataFrame containing the combined tide and sea level rise data.
    """
    # Remove any existing uniform boundary input files in the BG-Flood directory
    remove_existing_boundary_inputs(bg_flood_dir)
    # Log that the generation of uniform boundary model inputs has started
    log.info("Generating the uniform boundary model inputs for BG-Flood.")
    # Group the combined tide and sea level rise data by position
    grouped = tide_slr_data.groupby('position')
    # Iterate over each group and generate the required uniform boundary input file
    for position, group_data in grouped:
        # Extract the necessary columns from the group data
        input_data = group_data[['seconds', 'tide_slr_metres']]
        # Define the file path for the uniform boundary input file based on the position
        file_path = bg_flood_dir / f"{position}_bnd.txt"
        # Save the input data as a tab-separated text file at the specified file path
        input_data.to_csv(file_path, sep='\t', index=False, header=False)
        # Add the "# Water level boundary" line at the beginning of the uniform boundary input file
        with open(file_path, 'r+', encoding='utf-8') as file:
            content = file.read()
            file.seek(0, 0)
            file.write('# Water level boundary\n' + content)
    # Log a message indicating the successful generation of the uniform boundary model inputs
    log.info("Successfully generated the uniform boundary model inputs for BG-Flood.")
