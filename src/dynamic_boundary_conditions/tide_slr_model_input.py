# -*- coding: utf-8 -*-
"""
@Description: Generates the requested water level uniform boundary model input for BG-Flood.
@Author: sli229
"""

import logging
import pathlib

import pandas as pd

from src.dynamic_boundary_conditions import main_tide_slr

log = logging.getLogger(__name__)


def generate_uniform_boundary_input(bg_flood_dir: pathlib.Path, tide_slr_data: pd.DataFrame) -> None:
    """
    Generates the requested water level uniform boundary model input for BG-Flood.

    Parameters
    ----------
    bg_flood_dir : pathlib.Path
        The BG-Flood model directory.
    tide_slr_data : pd.DataFrame
        A DataFrame containing the combined tide and sea level rise data.

    Returns
    -------
    None
        This function does not return any value.
    """
    # Remove any existing uniform boundary input files in the BG-Flood directory
    main_tide_slr.remove_existing_boundary_input(bg_flood_dir)
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
        with open(file_path, 'r+') as file:
            content = file.read()
            file.seek(0, 0)
            file.write('# Water level boundary\n' + content)
    # Log a message indicating the successful generation of the uniform boundary model input
    log.info(f"Successfully generated the uniform boundary input for BG-Flood. Located in: {bg_flood_dir}")
