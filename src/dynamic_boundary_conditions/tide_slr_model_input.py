# -*- coding: utf-8 -*-
"""
@Description:
@Author: sli229
"""

import logging
import pathlib

import pandas as pd

from src.dynamic_boundary_conditions import main_tide_slr

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def generate_uniform_boundary_input(bg_flood_dir: pathlib.Path, tide_slr_data: pd.DataFrame):
    main_tide_slr.remove_existing_boundary_input(bg_flood_dir)
    grouped = tide_slr_data.groupby('position')
    for position, group_data in grouped:
        input_data = group_data[['seconds', 'tide_slr_metres']]
        file_path = bg_flood_dir / f"{position}_bnd.txt"
        input_data.to_csv(file_path, sep='\t', index=False, header=False)
        # Add "# Water level boundary" line at the beginning of the file
        with open(file_path, 'r+') as file:
            content = file.read()
            file.seek(0, 0)
            file.write('# Water level boundary\n' + content)
    log.info(f"Successfully generated the uniform boundary input for BG-Flood. Located in: {bg_flood_dir}")
