# -*- coding: utf-8 -*-
"""
@Script name: hyetograph.py
@Description: Create interactive hyetograph plots for sites within the catchment area.
@Author: pkh35
@Last modified by: sli229
@Last modified date: 28/11/2022
"""

import logging
import pathlib
import pandas as pd
import numpy as np
from typing import List, Literal
from math import floor, ceil
from scipy.interpolate import interp1d
import plotly.express as px

from src.digitaltwin import setup_environment
from src.dynamic_boundary_conditions import main_rainfall
from src.dynamic_boundary_conditions import hirds_rainfall_data_from_db

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def get_transposed_data(rain_data_in_catchment: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and transpose the retrieved scenario data from the database for sites within the catchment area and
    return in Pandas DataFrame format.

    Parameters
    ----------
    rain_data_in_catchment : pd.DataFrame
        Rainfall data for sites within the catchment area for a specified scenario retrieved from the database.
    """

    # drop unnecessary columns
    catchment_data = rain_data_in_catchment.drop(columns=["category", "rcp", "time_period", "ari", "aep"])
    # change column names
    for index, column_name in enumerate(catchment_data.columns):
        if column_name.endswith("m"):
            catchment_data.columns.values[index] = int(column_name[:-1])
        elif column_name.endswith("h"):
            catchment_data.columns.values[index] = int(column_name[:-1]) * 60
    # transpose data frame
    transposed_catchment_data = (
        catchment_data.set_index("site_id").rename_axis(None).transpose().rename_axis("duration_mins").reset_index()
    )
    return transposed_catchment_data


def get_interpolated_data(
        transposed_catchment_data: pd.DataFrame,
        increment_mins: int,
        interp_method: str) -> pd.DataFrame:
    """
    Perform temporal interpolation on the transposed scenario data for sites within the catchment area and
    return in Pandas DataFrame format.

    Parameters
    ----------
    transposed_catchment_data : pd.DataFrame
        Transposed scenario data retrieved from the database.
    increment_mins : int
        Time interval in minutes.
    interp_method : str
        Temporal interpolation method to be used. One of 'linear', 'nearest', 'nearest-up', 'zero',
 |      'slinear', 'quadratic', 'cubic', 'previous', or 'next'.
    """
    duration = transposed_catchment_data['duration_mins']
    duration_new = np.arange(increment_mins, duration.values[-1] + increment_mins, increment_mins)
    interp_catchment_data = pd.DataFrame(duration_new, columns=["duration_mins"])
    for column_num in range(1, len(transposed_catchment_data.columns)):
        depth = transposed_catchment_data.iloc[:, column_num]
        f_func = interp1d(duration, depth, kind=interp_method)
        site_id = depth.name
        depth_new = pd.Series(f_func(duration_new), name=site_id)
        interp_catchment_data = pd.concat([interp_catchment_data, depth_new], axis=1)
    return interp_catchment_data


def get_interp_incremental_data(interp_catchment_data: pd.DataFrame) -> pd.DataFrame:
    """
    Get the incremental rainfall data (difference between current and preceding cumulative rainfall)
    for sites within the catchment area and return in Pandas DataFrame format.

    Parameters
    ----------
    interp_catchment_data : pd.DataFrame
        Interpolated scenario data for sites within the catchment area.
    """
    interp_increment_data = interp_catchment_data.diff()[1:]
    interp_increment_data = pd.concat([interp_catchment_data.head(1), interp_increment_data])
    interp_increment_data.drop("duration_mins", axis=1, inplace=True)
    interp_increment_data = pd.concat(
        [interp_catchment_data["duration_mins"], interp_increment_data], axis=1)
    return interp_increment_data


def get_increment_data_for_storm_length(interp_increment_data: pd.DataFrame, storm_length_hrs: int) -> pd.DataFrame:
    """
    Get the incremental rainfall data for sites within the catchment area for a specific storm duration.

    Parameters
    ----------
    interp_increment_data : pd.DataFrame
        Incremental rainfall data for sites within the catchment area.
    storm_length_hrs : int
        Storm duration in hours.
    """
    storm_length_mins = storm_length_hrs * 60
    storm_length_filter = (interp_increment_data["duration_mins"] <= storm_length_mins)
    storm_length_data = interp_increment_data[storm_length_filter]
    return storm_length_data


def add_time_information(
        site_data: pd.DataFrame,
        time_to_peak_hrs: int,
        increment_mins: int,
        hyeto_method: Literal["alt_block", "chicago"]) -> pd.DataFrame:
    """
    Add time information (minutes column) to the hyetograph data based on the selected hyetograph method.

    Parameters
    ----------
    site_data : pd.DataFrame
        Hyetograph data for a rainfall site or gauge.
    time_to_peak_hrs : int
        The time in hours when rainfall is at its greatest (reaches maximum).
    increment_mins : int
        Time interval in minutes.
    hyeto_method : Literal["alt_block", "chicago"]
        Hyetograph method to be used. One of 'alt_block' or 'chicago', i.e., Alternating Block Method or
        Chicago Method.
    """
    time_to_peak_mins = time_to_peak_hrs * 60
    if hyeto_method == "alt_block":
        row_count = len(site_data)
        mins_from_peak_right = np.arange(1, ceil((row_count + 1) / 2)) * increment_mins
        if (row_count % 2) == 0:
            mins_from_peak_left = np.arange(0, floor((row_count + 1) / 2)) * -increment_mins
            mins_from_peak = [mins for sublist in zip(mins_from_peak_left, mins_from_peak_right) for mins in sublist]
        else:
            mins_from_peak_left = np.arange(1, floor((row_count + 1) / 2)) * -increment_mins
            mins_from_peak = [mins for sublist in zip(mins_from_peak_right, mins_from_peak_left) for mins in sublist]
            mins_from_peak.insert(0, 0)
        site_data = site_data.assign(mins=time_to_peak_mins + np.array(mins_from_peak))
    else:
        mins_start = time_to_peak_mins - site_data["duration_mins"][0]
        mins_end = time_to_peak_mins + site_data["duration_mins"][0]
        mins = np.arange(mins_start, mins_end, increment_mins / 2)
        site_data = site_data.assign(mins=mins)
    site_data = site_data.assign(hours=site_data["mins"] / 60)
    site_data = site_data.sort_values(by="mins", ascending=True)
    site_data = site_data.drop(columns=["duration_mins"]).reset_index(drop=True)
    return site_data


def transform_data_for_selected_method(
        storm_length_data: pd.DataFrame,
        time_to_peak_hrs: int,
        increment_mins: int,
        hyeto_method: Literal["alt_block", "chicago"]) -> List[pd.DataFrame]:
    """
    Transform the incremental rainfall data for sites within the catchment area for a selected hyetograph method.
    Returns a list of hyetograph data used to create individual hyetographs for each site within the
    catchment area.

    Parameters
    ----------
    storm_length_data : pd.DataFrame
        Incremental rainfall data for sites within the catchment area for a specific storm duration.
    time_to_peak_hrs : int
        The time in hours when rainfall is at its greatest (reaches maximum).
    increment_mins : int
        Time interval in minutes.
    hyeto_method : Literal["alt_block", "chicago"]
        Hyetograph method to be used. One of 'alt_block' or 'chicago', i.e., Alternating Block Method or
        Chicago Method.
    """
    hyetograph_sites_data = []
    for column_num in range(1, len(storm_length_data.columns)):
        site_data = storm_length_data.iloc[:, [0, column_num]]
        if hyeto_method == "alt_block":
            site_data = site_data.sort_values(by=site_data.columns[1], ascending=False)
            site_data = add_time_information(site_data, time_to_peak_hrs, increment_mins, hyeto_method)
        else:
            site_data_right = site_data.div(2)
            site_data_left = site_data_right[::-1]
            site_data = pd.concat([site_data_left, site_data_right]).reset_index(drop=True)
            site_data = add_time_information(site_data, time_to_peak_hrs, increment_mins, hyeto_method)
        hyetograph_sites_data.append(site_data)
    return hyetograph_sites_data


def get_hyetograph_sites_data(
        rain_data_in_catchment: pd.DataFrame,
        storm_length_hrs: int,
        time_to_peak_hrs: int,
        increment_mins: int,
        interp_method: str,
        hyeto_method: Literal["alt_block", "chicago"]) -> List[pd.DataFrame]:
    """
    Get all hyetograph data for a selected hyetograph method used to create individual hyetographs for
    each site within the catchment area.

    Parameters
    ----------
    rain_data_in_catchment : pd.DataFrame
        Rainfall data for sites within the catchment area for a specified scenario retrieved from the database.
    storm_length_hrs : int
        Storm duration in hours.
    time_to_peak_hrs : int
        The time in hours when rainfall is at its greatest (reaches maximum).
    increment_mins : int
        Time interval in minutes.
    interp_method : str
        Temporal interpolation method to be used. One of 'linear', 'nearest', 'nearest-up', 'zero',
        'slinear', 'quadratic', 'cubic', 'previous', or 'next'.
    hyeto_method : Literal["alt_block", "chicago"]
        Hyetograph method to be used. One of 'alt_block' or 'chicago', i.e., Alternating Block Method or
        Chicago Method.
    """
    hyeto_methods = ["alt_block", "chicago"]
    if hyeto_method not in hyeto_methods:
        log.error("Invalid hyetograph method.")
        raise ValueError("Invalid hyetograph method.")
    else:
        transposed_catchment_data = get_transposed_data(rain_data_in_catchment)
        interp_catchment_data = get_interpolated_data(transposed_catchment_data, increment_mins, interp_method)
        interp_increment_data = get_interp_incremental_data(interp_catchment_data)
        storm_length_data = get_increment_data_for_storm_length(interp_increment_data, storm_length_hrs)
        hyetograph_sites_data = transform_data_for_selected_method(
            storm_length_data, time_to_peak_hrs, increment_mins, hyeto_method)
    return hyetograph_sites_data


def hyetograph(hyetograph_sites_data: List[pd.DataFrame], ari: int):
    """
    Create interactive individual hyetograph plots for sites within the catchment area.

    Parameters
    ----------
    hyetograph_sites_data : List[pd.DataFrame]
        List of hyetograph data for sites within the catchment area.
    ari : float
        Storm average recurrence interval (ARI), i.e. 1.58, 2, 5, 10, 20, 30, 40, 50, 60, 80, 100, or 250.
    """
    for site_data in hyetograph_sites_data:
        site_id = site_data.columns.values[0]
        site_data["site_id"] = site_id
        site_data.columns.values[0] = "rain_depth_mm"
        hyeto_fig = px.bar(
            site_data,
            title=f"{ari}-year storm: site {site_id}",
            x="mins",
            y="rain_depth_mm",
            labels={"mins": "Time (Minutes)",
                    "rain_depth_mm": "Rainfall Depth (mm)"}
        )
        hyeto_fig.update_layout(
            title_font_size=20,
            title_x=0.5,
            bargap=0,
            updatemenus=[
                dict(
                    type="dropdown",
                    direction="down",
                    x=0.99,
                    y=0.99,
                    buttons=list([
                        dict(
                            args=["type", "bar"],
                            label="Bar Chart",
                            method="restyle"
                        ),
                        dict(
                            args=["type", "line"],
                            label="Line Chart",
                            method="restyle"
                        )
                    ]),
                )
            ]
        )
        hyeto_fig.show()


def main():
    catchment_file = pathlib.Path(r"src\dynamic_boundary_conditions\catchment_polygon.shp")
    rcp = None
    time_period = None
    ari = 50

    engine = setup_environment.get_database()
    catchment_polygon = main_rainfall.catchment_area_geometry_info(catchment_file)
    # Set idf to False for rain depth data and to True for rain intensity data
    rain_depth_in_catchment = hirds_rainfall_data_from_db.rainfall_data_from_db(
        engine, catchment_polygon, False, rcp, time_period, ari)

    hyetograph_sites_data = get_hyetograph_sites_data(
        rain_depth_in_catchment,
        storm_length_hrs=48,
        time_to_peak_hrs=60,
        increment_mins=10,
        interp_method="cubic",
        hyeto_method="alt_block")
    hyetograph(hyetograph_sites_data, ari)


if __name__ == "__main__":
    main()
