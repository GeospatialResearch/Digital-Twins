# -*- coding: utf-8 -*-
"""
@Script name: hyetograph.py
@Description: Create interactive hyetograph plots for sites within the catchment area.
@Author: pkh35
@Last modified by: sli229
@Last modified date: 12/12/2022
"""

import logging
import pathlib
import pandas as pd
import numpy as np
from typing import Literal
from math import floor, ceil
from scipy.interpolate import interp1d
import plotly.express as px
from src.digitaltwin import setup_environment
from src.dynamic_boundary_conditions import main_rainfall, thiessen_polygons, hirds_rainfall_data_from_db

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def get_transposed_data(rain_depth_in_catchment: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and transpose the retrieved scenario data from the database for sites within the catchment area and
    return in Pandas DataFrame format.

    Parameters
    ----------
    rain_depth_in_catchment : pd.DataFrame
        Rainfall depths for sites within the catchment area for a specified scenario retrieved from the database.
    """

    # drop unnecessary columns
    catchment_data = rain_depth_in_catchment.drop(columns=["category", "rcp", "time_period", "ari", "aep"])
    # change duration column names from text (e.g. 10m, 20m, ... , 1h, 24h) to
    # duration column names in minutes (e.g. 10, 20, ... , 60, 1440)
    for index, column_name in enumerate(catchment_data.columns):
        # convert duration column names in minutes (text) to duration columns in minutes (integer)
        if column_name.endswith("m"):
            catchment_data.columns.values[index] = int(column_name[:-1])
        # convert duration column names in hours (text) to duration columns in minutes (integer)
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
        Temporal interpolation method to be used. Refer to 'scipy.interpolate.interp1d()' for available methods.
        One of 'linear', 'nearest', 'nearest-up', 'zero', 'slinear', 'quadratic', 'cubic', 'previous', or 'next'.
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
    Get the incremental rainfall depths (difference between current and preceding cumulative rainfall)
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
    Get the incremental rainfall depths for sites within the catchment area for a specific storm duration.

    Parameters
    ----------
    interp_increment_data : pd.DataFrame
        Incremental rainfall depths for sites within the catchment area.
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
    Add time information (seconds, minutes, and hours column) to the hyetograph data based on the
    selected hyetograph method.

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
        # Alternating Block Method: the maximum incremental rainfall depths is placed at the peak position (center),
        # the remaining incremental rainfall depths are arranged alternatively in descending order after and before
        # the peak in turn.
        row_count = len(site_data)
        # Calculate minutes from peak for all incremental rainfall depths data
        mins_from_peak_right = np.arange(1, ceil((row_count + 1) / 2)) * increment_mins
        if (row_count % 2) == 0:
            mins_from_peak_left = np.arange(0, floor((row_count + 1) / 2)) * -increment_mins
            mins_from_peak = [mins for sublist in zip(mins_from_peak_left, mins_from_peak_right) for mins in sublist]
        else:
            mins_from_peak_left = np.arange(1, floor((row_count + 1) / 2)) * -increment_mins
            mins_from_peak = [mins for sublist in zip(mins_from_peak_right, mins_from_peak_left) for mins in sublist]
            mins_from_peak.insert(0, 0)
        # Add time (minutes) information using minutes from peak in order to allocate incremental rainfall depths
        site_data = site_data.assign(mins=time_to_peak_mins + np.array(mins_from_peak))
    else:
        # Chicago Method: the initial incremental rainfall depths is placed at the peak position and split in half
        # (left and right), the next incremental rainfall depths are further split in half and arranged before and after
        # (left and right) of the previous split incremental rainfall depths.
        # Add time (minutes) information in order to allocate the split incremental rainfall depths
        mins_start = time_to_peak_mins - site_data["duration_mins"][0]
        mins_end = time_to_peak_mins + site_data["duration_mins"][0]
        mins = np.arange(mins_start, mins_end, increment_mins / 2)
        site_data = site_data.assign(mins=mins)
    # Add extra time information, i.e. hours and seconds columns
    site_data = site_data.assign(hours=site_data["mins"] / 60,
                                 seconds=site_data["mins"] * 60)
    site_data = site_data.sort_values(by="seconds", ascending=True)
    site_data = site_data.drop(columns=["duration_mins"]).reset_index(drop=True)
    return site_data


def transform_data_for_selected_method(
        storm_length_data: pd.DataFrame,
        time_to_peak_hrs: int,
        increment_mins: int,
        hyeto_method: Literal["alt_block", "chicago"]) -> pd.DataFrame:
    """
    Transform the storm length incremental rainfall depths for sites within the catchment area based on
    the selected hyetograph method and returns in Pandas DataFrame format.

    Parameters
    ----------
    storm_length_data : pd.DataFrame
        Incremental rainfall depths for sites within the catchment area for a specific storm duration.
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
            # Alternating Block Method: the maximum incremental rainfall depths is placed at the peak position (center),
            # the remaining incremental rainfall depths are arranged alternatively in descending order after and before
            # the peak in turn.
            site_data = site_data.sort_values(by=site_data.columns[1], ascending=False)
        else:
            # Chicago Method: the initial incremental rainfall depths is placed at the peak position and split in half
            # (left and right), the next incremental rainfall depths are further split in half and arranged before and
            # after (left and right) of the previous split incremental rainfall depths.
            site_data_right = site_data.div(2)
            site_data_left = site_data_right[::-1]
            site_data = pd.concat([site_data_left, site_data_right]).reset_index(drop=True)
        site_data = add_time_information(site_data, time_to_peak_hrs, increment_mins, hyeto_method)
        hyetograph_sites_data.append(site_data)
    hyetograph_data = pd.concat(hyetograph_sites_data, axis=1, ignore_index=False)
    hyetograph_data = hyetograph_data.loc[:, ~hyetograph_data.columns.duplicated(keep="last")]
    return hyetograph_data


def get_hyetograph_data(
        rain_depth_in_catchment: pd.DataFrame,
        storm_length_hrs: int,
        time_to_peak_hrs: int,
        increment_mins: int,
        interp_method: str,
        hyeto_method: Literal["alt_block", "chicago"]) -> pd.DataFrame:
    """
    Get hyetograph data for all sites within the catchment area and returns in Pandas DataFrame format.

    Parameters
    ----------
    rain_depth_in_catchment : pd.DataFrame
        Rainfall depths for sites within the catchment area for a specified scenario retrieved from the database.
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
        raise ValueError(f"Invalid hyetograph method. '{hyeto_method}' not in {hyeto_methods}")
    if increment_mins < 10:
        raise ValueError(f"Increment minute {increment_mins} is out of range, needs to be at least 10.")
    transposed_catchment_data = get_transposed_data(rain_depth_in_catchment)
    interp_catchment_data = get_interpolated_data(transposed_catchment_data, increment_mins, interp_method)
    interp_increment_data = get_interp_incremental_data(interp_catchment_data)
    storm_length_data = get_increment_data_for_storm_length(interp_increment_data, storm_length_hrs)
    hyetograph_data = transform_data_for_selected_method(
        storm_length_data, time_to_peak_hrs, increment_mins, hyeto_method)
    return hyetograph_data


def hyetograph(hyetograph_data: pd.DataFrame, ari: int):
    """
    Create interactive individual hyetograph plots for sites within the catchment area.

    Parameters
    ----------
    hyetograph_data : pd.DataFrame
        Hyetograph data for sites within the catchment area.
    ari : float
        Storm average recurrence interval (ARI), i.e. 1.58, 2, 5, 10, 20, 30, 40, 50, 60, 80, 100, or 250.
    """
    for site_id in hyetograph_data.columns.values[:-3]:
        hyeto_site_data = hyetograph_data[[f"{site_id}", "mins", "hours", "seconds"]]
        hyeto_site_data.columns.values[0] = "rain_depth_mm"
        hyeto_fig = px.bar(
            hyeto_site_data,
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
    # Catchment polygon
    catchment_file = pathlib.Path(r"selected_polygon.geojson")
    catchment_polygon = main_rainfall.catchment_area_geometry_info(catchment_file)
    # Connect to the database
    engine = setup_environment.get_database()
    # Get all rainfall sites (thiessen polygons) coverage areas that are within the catchment area
    sites_in_catchment = thiessen_polygons.thiessen_polygons_from_db(engine, catchment_polygon)
    # Requested scenario
    rcp = 2.6
    time_period = "2031-2050"
    ari = 100
    # For a requested scenario, get all rainfall data for sites within the catchment area from the database
    # Set idf to False for rain depth data and to True for rain intensity data
    rain_depth_in_catchment = hirds_rainfall_data_from_db.rainfall_data_from_db(
        engine, sites_in_catchment, rcp, time_period, ari, idf=False)
    # Get hyetograph data for all sites within the catchment area
    hyetograph_data = get_hyetograph_data(
        rain_depth_in_catchment,
        storm_length_hrs=48,
        time_to_peak_hrs=24,
        increment_mins=10,
        interp_method="cubic",
        hyeto_method="chicago")
    # Create interactive hyetograph plots for sites within the catchment area
    hyetograph(hyetograph_data, ari)


if __name__ == "__main__":
    main()
