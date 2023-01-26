import unittest
import pandas as pd
import numpy as np
from typing import List
from unittest.mock import patch
import pathlib
from shapely.geometry import Polygon

import src.dynamic_boundary_conditions.hyetograph
from src.dynamic_boundary_conditions import hyetograph


class HyetographTest(unittest.TestCase):
    """Tests for hyetograph.py."""

    @classmethod
    def setUpClass(cls):
        cls.rain_depth_in_catchment = pd.read_csv(
            r"tests/test_dynamic_boundary_conditions/data/rain_depth_in_catchment.txt")
        cls.transposed_catchment_data = pd.read_csv(
            r"tests/test_dynamic_boundary_conditions/data/transposed_catchment_data.txt")
        cls.interp_catchment_data = pd.read_csv(
            r"tests/test_dynamic_boundary_conditions/data/interp_catchment_data.txt")
        cls.interp_increment_data = pd.read_csv(
            r"tests/test_dynamic_boundary_conditions/data/interp_increment_data.txt")
        cls.storm_length_data = pd.read_csv(
            r"tests/test_dynamic_boundary_conditions/data/storm_length_data.txt")
        cls.site_data_alt_block = pd.read_csv(
            r"tests/test_dynamic_boundary_conditions/data/site_data_alt_block.txt")
        cls.site_data_chicago = pd.read_csv(
            r"tests/test_dynamic_boundary_conditions/data/site_data_chicago.txt")

        cls.increment_mins = 10
        cls.interp_method = "cubic"
        cls.storm_length_mins = 2880
        cls.time_to_peak_mins = 1440
        cls.hyeto_method_alt_block = hyetograph.HyetoMethod.ALT_BLOCK
        cls.hyeto_method_chicago = hyetograph.HyetoMethod.CHICAGO

    def test_get_transposed_data_matching_site_ids(self):
        transposed_catchment_data = hyetograph.get_transposed_data(self.rain_depth_in_catchment)
        orig_site_ids = self.rain_depth_in_catchment["site_id"].to_list()
        tps_site_ids = transposed_catchment_data.columns[1:].to_list()
        self.assertEqual(orig_site_ids, tps_site_ids)

    def test_get_transposed_data_matching_duration_mins(self):
        transposed_catchment_data = hyetograph.get_transposed_data(self.rain_depth_in_catchment)
        org_duration_mins = []
        for column_name in self.rain_depth_in_catchment.columns:
            if column_name[0].isdigit():
                if column_name.endswith("m"):
                    org_duration_mins.append(int(column_name[:-1]))
                elif column_name.endswith("h"):
                    org_duration_mins.append(int(column_name[:-1]) * 60)
        trans_duration_mins = transposed_catchment_data["duration_mins"].to_list()
        self.assertEqual(org_duration_mins, trans_duration_mins)

    def test_get_transposed_data_correct_corner_values(self):
        transposed_catchment_data = hyetograph.get_transposed_data(self.rain_depth_in_catchment)
        original_data = self.rain_depth_in_catchment.drop(
            columns=["site_id", "category", "rcp", "time_period", "ari", "aep"])
        orig_top_left = original_data.iloc[0][0]
        orig_top_right = original_data.iloc[0][-1]
        orig_bottom_left = original_data.iloc[-1][0]
        orig_bottom_right = original_data.iloc[-1][-1]
        transposed_data = transposed_catchment_data.drop(columns="duration_mins")
        tps_top_left = transposed_data.iloc[0][0]
        tps_top_right = transposed_data.iloc[0][-1]
        tps_bottom_left = transposed_data.iloc[-1][0]
        tps_bottom_right = transposed_data.iloc[-1][-1]
        self.assertEqual(orig_top_left, tps_top_left)
        self.assertNotEqual(orig_top_right, tps_top_right)
        self.assertNotEqual(orig_bottom_left, tps_bottom_left)
        self.assertEqual(orig_bottom_right, tps_bottom_right)
        self.assertEqual(orig_top_right, tps_bottom_left)
        self.assertEqual(orig_bottom_left, tps_top_right)

    def test_get_interpolated_data_invalid_increment_mins(self):
        increment_mins_list = list(range(0, 10)) + list(range(7201, 7211))
        for increment_mins in increment_mins_list:
            with self.assertRaises(ValueError) as context:
                hyetograph.get_interpolated_data(
                    self.transposed_catchment_data, increment_mins=increment_mins, interp_method=self.interp_method)
            self.assertEqual(
                f"Increment minute {increment_mins} is out of range, needs to be between 10 and 7200.",
                str(context.exception))

    def test_get_interpolated_data_invalid_interp_method(self):
        interp_method_list = ["invalid", "test", "abc", "123"]
        for interp_method in interp_method_list:
            with self.assertRaises(ValueError) as context:
                hyetograph.get_interpolated_data(
                    self.transposed_catchment_data, increment_mins=self.increment_mins, interp_method=interp_method)
            self.assertEqual(
                f"Invalid interpolation method: '{interp_method}'. "
                f"Refer to 'scipy.interpolate.interp1d()' for available methods.",
                str(context.exception))

    def test_get_interpolated_data_valid_mins_and_method(self):
        increment_mins_list = list(range(10, 7201))
        for increment_mins in increment_mins_list:
            interp_catchment_data = hyetograph.get_interpolated_data(
                self.transposed_catchment_data, increment_mins=increment_mins, interp_method=self.interp_method)
            self.assertGreater(len(interp_catchment_data), 0)

    def test_get_interp_incremental_data_row_difference(self):

        def get_interp_catchment_data_row_difference(index: int) -> List[float]:
            if index == 0:
                row_diff = self.interp_catchment_data.iloc[index]
            else:
                row_diff = (self.interp_catchment_data.iloc[index] - self.interp_catchment_data.iloc[index - 1])
                row_diff["duration_mins"] = self.interp_catchment_data.iloc[index]["duration_mins"]
            return row_diff.to_list()

        interp_increment_data = hyetograph.get_interp_incremental_data(self.interp_catchment_data)
        self.assertEqual(self.interp_catchment_data.shape, interp_increment_data.shape)

        expected_first_row = get_interp_catchment_data_row_difference(index=0)
        actual_first_row = interp_increment_data.iloc[0].to_list()
        self.assertEqual(expected_first_row, actual_first_row)

        expected_second_row = get_interp_catchment_data_row_difference(index=1)
        actual_second_row = interp_increment_data.iloc[1].to_list()
        self.assertEqual(expected_second_row, actual_second_row)

        expected_second_last_row = get_interp_catchment_data_row_difference(index=-2)
        actual_second_last_row = interp_increment_data.iloc[-2].to_list()
        self.assertEqual(expected_second_last_row, actual_second_last_row)

        expected_last_row = get_interp_catchment_data_row_difference(index=-1)
        actual_last_row = interp_increment_data.iloc[-1].to_list()
        self.assertEqual(expected_last_row, actual_last_row)

    def test_get_storm_length_increment_data_invalid_storm_length_mins(self):
        min_storm_length_mins = self.interp_increment_data["duration_mins"].iloc[0]
        storm_lengths_mins_list = list(range(0, min_storm_length_mins))
        for storm_lengths_mins in storm_lengths_mins_list:
            with self.assertRaises(ValueError) as context:
                hyetograph.get_storm_length_increment_data(
                    self.interp_increment_data, storm_length_mins=storm_lengths_mins)
            self.assertEqual(
                f"Storm duration (storm_length_mins) needs to be at least '{int(min_storm_length_mins)}'.",
                str(context.exception))

    def test_get_storm_length_increment_data_valid_storm_length_mins(self):
        min_storm_length_mins = self.interp_increment_data["duration_mins"].iloc[0]
        storm_lengths_mins_list = list(range(min_storm_length_mins, 7261))
        for storm_lengths_mins in storm_lengths_mins_list:
            storm_length_data = hyetograph.get_storm_length_increment_data(
                self.interp_increment_data, storm_length_mins=storm_lengths_mins)
            self.assertGreater(len(storm_length_data), 0)

    def test_add_time_information_invalid_time_to_peak_mins(self):
        combined_list = [(self.site_data_alt_block, self.hyeto_method_alt_block),
                         (self.site_data_chicago, self.hyeto_method_chicago)]

        min_time_to_peak_mins = int(self.storm_length_mins / 2)
        time_to_peak_mins_list = list(range(0, min_time_to_peak_mins))

        for site_data, hyeto_method in combined_list:
            for time_to_peak_mins in time_to_peak_mins_list:
                with self.assertRaises(ValueError) as context_alt_block:
                    hyetograph.add_time_information(
                        site_data=site_data,
                        storm_length_mins=self.storm_length_mins,
                        time_to_peak_mins=time_to_peak_mins,
                        increment_mins=self.increment_mins,
                        hyeto_method=hyeto_method)
                    self.assertEqual(
                        "'time_to_peak_mins' (time in minutes when rainfall is at its greatest) needs to be "
                        "at least half of 'storm_length_mins' (storm duration).",
                        str(context_alt_block.exception))

    def test_add_time_information_increment_mins_correct_increment_mins_diff(self):
        combined_list = [(self.site_data_alt_block, self.hyeto_method_alt_block),
                         (self.site_data_chicago, self.hyeto_method_chicago)]

        for site_data, hyeto_method in combined_list:
            data_output = hyetograph.add_time_information(
                site_data=site_data,
                storm_length_mins=self.storm_length_mins,
                time_to_peak_mins=self.time_to_peak_mins,
                increment_mins=self.increment_mins,
                hyeto_method=hyeto_method)
            data_output_mins = data_output["mins"].to_list()
            mins_diff = np.unique(np.diff(data_output_mins))
            if hyeto_method == "alt_block":
                self.assertEqual(self.increment_mins, mins_diff)
            else:
                self.assertEqual(self.increment_mins / 2, mins_diff)

    def test_add_time_information_correct_time_calculation(self):
        combined_list = [(self.site_data_alt_block, self.hyeto_method_alt_block),
                         (self.site_data_chicago, self.hyeto_method_chicago)]

        for site_data, hyeto_method in combined_list:
            site_data_output = hyetograph.add_time_information(
                site_data=site_data,
                storm_length_mins=self.storm_length_mins,
                time_to_peak_mins=self.time_to_peak_mins,
                increment_mins=self.increment_mins,
                hyeto_method=hyeto_method)
            if hyeto_method == "alt_block":
                self.assertEqual(self.increment_mins, site_data_output["mins"][0])
                self.assertEqual(self.increment_mins / 60, site_data_output["hours"][0])
                self.assertEqual(self.increment_mins * 60, site_data_output["seconds"][0])
            else:
                self.assertEqual(self.increment_mins / 2, site_data_output["mins"][0])
                self.assertEqual(self.increment_mins / 2 / 60, site_data_output["hours"][0])
                self.assertEqual(self.increment_mins / 2 * 60, site_data_output["seconds"][0])

    @patch("src.dynamic_boundary_conditions.hyetograph.get_storm_length_increment_data")
    def test_transform_data_for_selected_method_correct_output_structure(self, mock_storm_length_data):
        mock_storm_length_data.return_value = self.storm_length_data
        site_ids = self.interp_increment_data.columns[1:].tolist()
        hyeto_method_list = [self.hyeto_method_alt_block, self.hyeto_method_chicago]
        for hyeto_method in hyeto_method_list:
            hyetograph_depth = hyetograph.transform_data_for_selected_method(
                interp_increment_data=pd.DataFrame(),
                storm_length_mins=self.storm_length_mins,
                time_to_peak_mins=self.time_to_peak_mins,
                increment_mins=self.increment_mins,
                hyeto_method=hyeto_method)

            first_row = hyetograph_depth.iloc[0, :-3]
            last_row = hyetograph_depth.iloc[-1, :-3]
            result = first_row.equals(last_row)

            self.assertFalse(result) if hyeto_method == "alt_block" else self.assertTrue(result)
            self.assertEqual(site_ids, hyetograph_depth.columns.values[:-3].tolist())
            self.assertEqual(["mins", "hours", "seconds"], hyetograph_depth.columns.values[-3:].tolist())
            self.assertEqual(self.storm_length_mins, hyetograph_depth["mins"].iloc[-1])


if __name__ == "__main__":
    unittest.main()
