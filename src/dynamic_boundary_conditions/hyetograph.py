import logging
import pathlib
import pandas as pd
import numpy as np
from typing import List
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
    catchment_data = rain_data_in_catchment.drop(columns=["category", "rcp", "time_period", "ari", "aep"])

    for index, column_name in enumerate(catchment_data.columns):
        if column_name.endswith("m"):
            catchment_data.columns.values[index] = int(column_name[:-1])
        elif column_name.endswith("h"):
            catchment_data.columns.values[index] = int(column_name[:-1]) * 60

    transposed_catchment_data = (
        catchment_data.set_index("site_id").rename_axis(None).transpose().rename_axis("duration_mins").reset_index()
    )
    return transposed_catchment_data


def get_interpolated_data(
        transposed_catchment_data: pd.DataFrame,
        increment_mins: int,
        interp_method: str) -> pd.DataFrame:
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
    interp_increment_data = interp_catchment_data.diff()[1:]
    interp_increment_data = pd.concat([interp_catchment_data.head(1), interp_increment_data])
    interp_increment_data.drop("duration_mins", axis=1, inplace=True)
    interp_increment_data = pd.concat(
        [interp_catchment_data["duration_mins"], interp_increment_data], axis=1)
    return interp_increment_data


def get_increment_data_for_storm_length(interp_increment_data: pd.DataFrame, storm_length_hrs: int) -> pd.DataFrame:
    storm_length_mins = storm_length_hrs * 60
    storm_length_filter = (interp_increment_data["duration_mins"] <= storm_length_mins)
    storm_length_data = interp_increment_data[storm_length_filter]
    return storm_length_data


def add_time_information(
        site_data: pd.DataFrame,
        time_to_peak_hrs: int,
        increment_mins: int) -> pd.DataFrame:
    time_to_peak_mins = time_to_peak_hrs * 60
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
    return site_data


def transform_data_for_selected_method(
        storm_length_data: pd.DataFrame,
        time_to_peak_hrs: int,
        increment_mins: int,
        hyeto_method: str) -> List[pd.DataFrame]:
    time_to_peak_mins = time_to_peak_hrs * 60
    hyetograph_sites_data = []
    for column_num in range(1, len(storm_length_data.columns)):
        site_data = storm_length_data.iloc[:, [0, column_num]]
        if hyeto_method == "alt_block":
            site_data = site_data.sort_values(by=site_data.columns[1], ascending=False)
            site_data = add_time_information(site_data, time_to_peak_hrs, increment_mins)
        elif hyeto_method == "chicago":
            site_data_right = site_data.div(2)
            site_data_left = site_data_right[::-1]
            site_data_left = site_data_left.assign(mins=time_to_peak_mins - site_data_left["duration_mins"])
            site_data_left_last_min = site_data_left["mins"].iloc[-1]
            site_data_right = site_data_right.assign(mins=site_data_left_last_min + site_data_right["duration_mins"])
            site_data = pd.concat([site_data_left, site_data_right])
        site_data = site_data.assign(hours=site_data["mins"] / 60)
        site_data = site_data.sort_values(by="mins", ascending=True)
        site_data = site_data.drop(columns=["duration_mins"]).reset_index(drop=True)
        hyetograph_sites_data.append(site_data)
    return hyetograph_sites_data


def get_hyetograph_sites_data(
        rain_data_in_catchment: pd.DataFrame,
        storm_length_hrs: int = 48,
        time_to_peak_hrs: int = 60,
        increment_mins: int = 10,
        interp_method: str = "cubic",
        hyeto_method: str = "alt_block") -> List[pd.DataFrame]:
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
    for site_data in hyetograph_sites_data:
        site_id = site_data.columns.values[0]
        site_data["site_id"] = site_id
        site_data.columns.values[0] = "rain_depth_mm"
        hyeto_fig = px.bar(
            site_data,
            title=f"{ari}-year storm: site {site_id}",
            x="mins",  # "hours",
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
    rcp = 2.6  # None  # 2.6
    time_period = "2031-2050"  # None  # "2031-2050"
    ari = 50  # 100

    engine = setup_environment.get_database()
    catchment_polygon = main_rainfall.catchment_area_geometry_info(catchment_file)
    # Set idf to False for rain depth data and to True for rain intensity data
    rain_depth_in_catchment = hirds_rainfall_data_from_db.rainfall_data_from_db(
        engine, catchment_polygon, False, rcp, time_period, ari)

    hyetograph_sites_data = get_hyetograph_sites_data(
        rain_depth_in_catchment,
        storm_length_hrs=48,  # 48,
        time_to_peak_hrs=60,  # 60
        increment_mins=10,  # 10,
        interp_method="cubic",
        hyeto_method="chicago")
    hyetograph(hyetograph_sites_data, ari)


if __name__ == "__main__":
    main()
