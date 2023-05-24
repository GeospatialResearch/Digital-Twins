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


def remove_existing_river_inputs(bg_flood_path: pathlib.Path):
    # iterate through all files in the directory
    for file_path in bg_flood_path.glob('river[0-9]*_*.txt'):
        # remove the file
        file_path.unlink()


def generate_river_model_input(bg_flood_path: pathlib.Path, hydrograph_data: gpd.GeoDataFrame):
    remove_existing_river_inputs(bg_flood_path)
    grouped = hydrograph_data.groupby(
        ['target_point_no', hydrograph_data['target_point'].to_wkt(), 'res_no', 'areakm2'],
        sort=False)
    for group_name, group_data in grouped:
        target_point_no, _, res_no, _ = group_name
        group_data['target_cell'] = group_data['target_point'].buffer(distance=res_no / 2, cap_style=3)
        target_cell = group_data['target_cell'].unique()[0]
        x_min, y_min, x_max, y_max = target_cell.bounds
        input_data = group_data[['seconds', 'flow']].reset_index(drop=True)
        file_path = bg_flood_path / f"river{target_point_no}_{x_min}_{x_max}_{y_min}_{y_max}.txt"
        input_data.to_csv(file_path, index=False, header=False)
    log.info(f"Successfully generated river model inputs for BG-Flood. Located in: {bg_flood_path}")


def main():
    # Connect to the database
    engine = setup_environment.get_database()
    # Get catchment area
    catchment_area = main_river.get_catchment_area(r"selected_polygon.geojson")

    # --- river_data_to_from_db.py -------------------------------------------------------------------------------------
    # Store REC1 data to db
    rec1_data_dir = "U:/Research/FloodRiskResearch/DigitalTwin/stored_data/rec1_data"
    river_data_to_from_db.store_rec1_data_to_db(engine, rec1_data_dir)
    # Store sea-draining catchments data to db
    river_data_to_from_db.store_sea_drain_catchments_to_db(engine, layer_id=99776)
    # Get REC1 data from db covering area of interest
    rec1_data = river_data_to_from_db.get_rec1_data_from_db(engine, catchment_area)

    # --- river_network_for_aoi.py -------------------------------------------------------------------------------------
    # Create REC1 network covering area of interest
    rec1_network_data = river_network_for_aoi.create_rec1_network_data_for_aoi(rec1_data)
    rec1_network = river_network_for_aoi.build_rec1_network_for_aoi(rec1_network_data)
    # Get REC1 boundary points crossing the catchment boundary
    rec1_network_data_on_bbox = river_network_for_aoi.get_rec1_network_data_on_bbox(catchment_area, rec1_network_data)

    # --- osm_waterways.py ---------------------------------------------------------------------------------------------
    # Get OSM waterways data for requested catchment area
    osm_waterways_data = osm_waterways.get_waterways_data_from_osm(catchment_area)
    # Get OSM boundary points crossing the catchment boundary
    osm_waterways_data_on_bbox = osm_waterways.get_osm_waterways_data_on_bbox(catchment_area, osm_waterways_data)

    # --- river_osm_combine.py -----------------------------------------------------------------------------------------
    # Find closest OSM waterway to REC1 rivers and get model input target point
    matched_data = river_osm_combine.get_matched_data_with_target_point(
        rec1_network_data_on_bbox, osm_waterways_data_on_bbox, distance_threshold_m=300)

    # --- hydrograph.py ------------------------------------------------------------------------------------------------
    # Get hydrograph data
    hydrograph_data = hydrograph.get_hydrograph_data(
        matched_data,
        river_length_mins=2880,
        time_to_peak_mins=1440,
        maf=True,
        ari=None,
        bound=BoundType.MIDDLE)
    print(hydrograph_data)

    # --- Generate river model inputs for BG-Flood ---------------------------------------------------------------------
    bg_flood_path = config.get_env_variable("FLOOD_MODEL_DIR", cast_to=pathlib.Path)
    generate_river_model_input(bg_flood_path, hydrograph_data)


if __name__ == "__main__":
    main()
