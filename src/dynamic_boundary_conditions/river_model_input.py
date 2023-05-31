import logging
import pathlib

import geopandas as gpd
import pandas as pd

from src import config
from src.digitaltwin import setup_environment
from src.dynamic_boundary_conditions.river_enum import BoundType
from src.dynamic_boundary_conditions import (
    main_river,
    river_data_to_from_db,
    river_network_for_aoi,
    osm_waterways,
    river_osm_combine,
    hydrograph
)

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)

pd.set_option('expand_frame_repr', False)


def remove_existing_river_inputs(bg_flood_dir: pathlib.Path):
    # iterate through all files in the directory
    for file_path in bg_flood_dir.glob('river[0-9]*.txt'):
        # remove the file
        file_path.unlink()


def generate_river_model_input(bg_flood_dir: pathlib.Path, hydrograph_data: gpd.GeoDataFrame):
    remove_existing_river_inputs(bg_flood_dir)
    grouped = hydrograph_data.groupby(
        ['target_point_no', hydrograph_data['target_point'].to_wkt(), 'res_no', 'areakm2'],
        sort=False)
    for group_name, group_data in grouped:
        target_point_no, _, res_no, _ = group_name
        group_data['target_cell'] = group_data['target_point'].buffer(distance=res_no / 2, cap_style=3)
        target_cell = group_data['target_cell'].unique()[0]
        x_min, y_min, x_max, y_max = target_cell.bounds
        input_data = group_data[['seconds', 'flow']].reset_index(drop=True)
        file_path = bg_flood_dir / f"river{target_point_no}_{x_min}_{x_max}_{y_min}_{y_max}.txt"
        input_data.to_csv(file_path, index=False, header=False)
    log.info(f"Successfully generated river model inputs for BG-Flood. Located in: {bg_flood_dir}")
