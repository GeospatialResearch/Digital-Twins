import logging
from typing import List, Union
import re

import geopandas as gpd

from src.dynamic_boundary_conditions.river_enum import BoundType

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
    # TODO: modify code to incorporate actual method and align with rainfall/tide data
    min_time_to_peak_mins = river_length_mins / 2
    if time_to_peak_mins < min_time_to_peak_mins:
        raise ValueError(
            "'time_to_peak_mins' needs to be at least half of 'river_length_mins'.")
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
        data['mins'].extend(
            [time_to_peak_mins - min_time_to_peak_mins,
             time_to_peak_mins,
             time_to_peak_mins + min_time_to_peak_mins])
        data['flow'].extend([row['maf'] * 0.1, row['middle'], 0])
    hydrograph_data = gpd.GeoDataFrame(data, geometry="target_point", crs=flow_data.crs)
    hydrograph_data = hydrograph_data.assign(
        hours=hydrograph_data["mins"] / 60,
        seconds=hydrograph_data["mins"] * 60)
    hydrograph_data['flow'] = hydrograph_data.pop('flow')
    return hydrograph_data
