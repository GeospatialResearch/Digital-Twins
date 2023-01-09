import unittest
import pandas as pd
import pathlib
from shapely.geometry import Polygon
from src.dynamic_boundary_conditions import hyetograph


class HyetographTest(unittest.TestCase):
    """Tests for hyetograph.py."""

    @classmethod
    def setUpClass(cls):
        cls.rain_depth_in_catchment = pd.read_csv(
            r"tests/test_dynamic_boundary_conditions/data/rain_depth_in_catchment.csv")

    def test_get_transposed_data_matching_site_ids(self):
        orig_site_ids = self.rain_depth_in_catchment["site_id"].to_list()
        transposed_catchment_data = hyetograph.get_transposed_data(self.rain_depth_in_catchment)
        tps_site_ids = transposed_catchment_data.columns[1:].to_list()
        self.assertEqual(orig_site_ids, tps_site_ids)

    def test_get_transposed_data_matching_duration_mins(self):
        org_duration_mins = []
        for column_name in self.rain_depth_in_catchment.columns:
            if column_name[0].isdigit():
                if column_name.endswith("m"):
                    org_duration_mins.append(int(column_name[:-1]))
                elif column_name.endswith("h"):
                    org_duration_mins.append(int(column_name[:-1]) * 60)
        transposed_catchment_data = hyetograph.get_transposed_data(self.rain_depth_in_catchment)
        trans_duration_mins = transposed_catchment_data["duration_mins"].to_list()
        self.assertEqual(org_duration_mins, trans_duration_mins)

    def test_get_transposed_data_correct_corner_values(self):
        original_data = self.rain_depth_in_catchment.drop(
            columns=["site_id", "category", "rcp", "time_period", "ari", "aep"])
        orig_top_left = original_data.iloc[0][0]
        orig_top_right = original_data.iloc[0][-1]
        orig_bottom_left = original_data.iloc[-1][0]
        orig_bottom_right = original_data.iloc[-1][-1]

        transposed_data = hyetograph.get_transposed_data(self.rain_depth_in_catchment).drop(columns="duration_mins")
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


if __name__ == "__main__":
    unittest.main()
