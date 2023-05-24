import logging
from typing import List, Union
import re

import geopandas as gpd

from src.digitaltwin import setup_environment
from src.dynamic_boundary_conditions.river_enum import BoundType
from src.dynamic_boundary_conditions import (
    main_river,
    river_data_to_from_db,
    river_network_for_aoi,
    osm_waterways,
    river_osm_combine
)

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def rename_flow_data_columns(flow_data: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    new_col_names = []
    for col_name in flow_data.columns:
        if col_name.startswith('h_c18_'):
            new_col_name = re.sub('^h_c18_', 'flow_', col_name)
        elif col_name.startswith('hcse_'):
            new_col_name = re.sub('^hcse_', 'flow_se_', col_name)
        else:
            new_col_name = col_name
        new_col_name = re.sub('_yr$|y$', '', new_col_name)
        new_col_names.append(new_col_name)
    flow_data.columns = new_col_names
    return flow_data


def get_valid_ari_values(flow_data: gpd.GeoDataFrame) -> List[int]:
    valid_ari_values = []
    col_names = flow_data.columns
    pattern = re.compile(r'flow_(\d+)')
    for col_name in col_names:
        match = re.search(pattern, col_name)
        if match:
            ari_value = int(match.group(1))
            valid_ari_values.append(ari_value)
    return valid_ari_values


def get_selected_maf_ari_flow_data(
        flow_data: gpd.GeoDataFrame,
        maf: bool,
        ari: int = None) -> gpd.GeoDataFrame:
    if maf:
        selected_data = flow_data[
            ['target_point', 'res_no', 'areakm2', 'flow_maf', 'flow_se_maf']].copy()
        selected_data.rename(
            columns={'flow_maf': 'maf', 'flow_se_maf': 'flow_se'}, inplace=True)
        selected_data['middle'] = selected_data['maf']
    else:
        selected_data = flow_data[
            ['target_point', 'res_no', 'areakm2', 'flow_maf', f'flow_{ari}', f'flow_se_{ari}']].copy()
        selected_data.rename(
            columns={'flow_maf': 'maf', f'flow_{ari}': 'middle', f'flow_se_{ari}': 'flow_se'}, inplace=True)
    selected_data['lower'] = selected_data['middle'] - selected_data['flow_se']
    selected_data['upper'] = selected_data['middle'] + selected_data['flow_se']
    selected_data = selected_data.drop(columns=['flow_se']).reset_index(drop=True)
    selected_data['target_point_no'] = selected_data.index + 1
    return selected_data


def get_flow_data_for_hydrograph(
        matched_data: gpd.GeoDataFrame,
        maf: bool,
        ari: int = None,
        bound: BoundType = BoundType.MIDDLE) -> gpd.GeoDataFrame:
    selected_columns = ['objectid', 'id', 'target_point', 'res_no', 'areakm2'] + \
                       [col for col in matched_data.columns if col.startswith('h')]
    flow_data = matched_data[selected_columns]
    flow_data = rename_flow_data_columns(flow_data)
    if maf:
        if ari is not None:
            raise ValueError("'ari' value should not be provided when 'maf' is True.")
        selected_data = get_selected_maf_ari_flow_data(flow_data, maf, ari)
    else:
        if ari is None:
            raise ValueError("'ari' value must be provided when 'maf' is False.")
        # Get valid 'ari' values
        valid_ari_values = get_valid_ari_values(flow_data)
        if ari not in valid_ari_values:
            raise ValueError(f"Invalid 'ari' value: {ari}. Must be one of {valid_ari_values}.")
        selected_data = get_selected_maf_ari_flow_data(flow_data, maf, ari)
    selected_flow_data = selected_data[
        ['target_point_no', 'target_point', 'res_no', 'areakm2', 'maf', f'{bound.value}']]
    return selected_flow_data


def get_hydrograph_data(
        matched_data: gpd.GeoDataFrame,
        river_length_mins: int,
        time_to_peak_mins: Union[int, float],
        maf: bool,
        ari: Union[int, None] = None,
        bound: BoundType = BoundType.MIDDLE) -> gpd.GeoDataFrame:
    flow_data = get_flow_data_for_hydrograph(matched_data, maf, ari, bound)
    data = {
        'target_point_no': [],
        'target_point': [],
        'res_no': [],
        'areakm2': [],
        'mins': [],
        'flow': []
    }
    for _, row in flow_data.iterrows():
        data['target_point_no'].extend([row['target_point_no']] * 3)
        data['target_point'].extend([row['target_point']] * 3)
        data['res_no'].extend([row['res_no']] * 3)
        data['areakm2'].extend([row['areakm2']] * 3)
        data['mins'].extend([0, time_to_peak_mins, river_length_mins])
        data['flow'].extend([row['maf'] * 0.1, row['middle'], 0])
    hydrograph_data = gpd.GeoDataFrame(data, geometry="target_point", crs=flow_data.crs)
    hydrograph_data = hydrograph_data.assign(
        hours=hydrograph_data["mins"] / 60,
        seconds=hydrograph_data["mins"] * 60)
    return hydrograph_data


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
    hydrograph_data = get_hydrograph_data(
        matched_data,
        river_length_mins=2880,
        time_to_peak_mins=1440,
        maf=True,
        ari=None,
        bound=BoundType.MIDDLE)
    print(hydrograph_data)


if __name__ == "__main__":
    main()
