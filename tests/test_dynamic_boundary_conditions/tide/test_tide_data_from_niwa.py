import unittest
from unittest.mock import patch
from typing import List, Dict

from shapely import LineString
from datetime import date, timedelta
from shapely.wkt import loads
import pandas as pd
import geopandas as gpd

import numpy as np

from src.dynamic_boundary_conditions.tide import tide_data_from_niwa


class TideDataFromNiwaTest(unittest.TestCase):

    query_loc_row = None

    @classmethod
    def setUpClass(cls):
        data_dir = "tests/test_dynamic_boundary_conditions/tide/data"
        cls.query_loc_row = pd.read_csv(f"{data_dir}/query_loc_row.txt")
        cls.query_loc_row['geometry'] = cls.query_loc_row['geometry'].apply(loads)
        cls.gdf = gpd.GeoDataFrame(cls.query_loc_row, geometry='geometry')

    def test_get_query_loc_coords_position(self):
        actual_output = tide_data_from_niwa.get_query_loc_coords_position(self.gdf)
        expected_output = (-43.39127633722616, 172.7098878483352, 'right')
        self.assertEqual(actual_output, expected_output)

    def test_valid_input_get_date_ranges(self):
        # Test with default values
        result = tide_data_from_niwa.get_date_ranges()
        expected_result = {date.today(): 31}
        self.assertEqual(result, expected_result)

        # Test with custom values
        custom_start_date = date(2024, 1, 3)
        custom_total_days = 365
        custom_days_per_call = 31

        result = tide_data_from_niwa.get_date_ranges(custom_start_date, custom_total_days, custom_days_per_call)

        expected_result = {}
        current_date = custom_start_date
        while current_date < custom_start_date + timedelta(days=custom_total_days):
            end_date = min(current_date + timedelta(days=custom_days_per_call - 1),
                           custom_start_date + timedelta(days=custom_total_days - 1))
            expected_result[current_date] = (end_date - current_date).days + 1
            current_date = end_date + timedelta(days=1)

        # Adjust the expected result to handle the last chunk with fewer days
        remaining_days = custom_total_days - sum(expected_result.values())
        if remaining_days > 0:
            expected_result[current_date] = remaining_days

        # Add additional adjustment for the case where the last chunk has the same number of days as the preceding
        # chunks
        if len(expected_result) > 1 and remaining_days == custom_days_per_call:
            del expected_result[current_date - timedelta(days=1)]

        self.assertEqual(result, expected_result)

    def test_invalid_total_days_get_date_ranges(self):
        # Test with total_days less than 1
        with self.assertRaises(ValueError):
            tide_data_from_niwa.get_date_ranges(total_days=0)

    def test_invalid_days_per_call_get_date_ranges(self):
        # Test with days_per_call greater than 31
        with self.assertRaises(ValueError):
            tide_data_from_niwa.get_date_ranges(days_per_call=32)

        # Test with days_per_call less than 1
        with self.assertRaises(ValueError):
            tide_data_from_niwa.get_date_ranges(days_per_call=0)


if __name__ == "__main__":
    unittest.main()

