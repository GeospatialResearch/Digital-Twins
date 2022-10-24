import unittest
from unittest.mock import patch
import pathlib
from shapely.geometry import Polygon
import geopandas as gpd
from src.dynamic_boundary_conditions import hyetograph, rainfall_sites


class HyetographTest(unittest.TestCase):

    def test_catchment_area_geometry_info_correct_type(self):
        catchment_file_path = pathlib.Path(r"tests/test_dynamic_boundary_conditions/data/catchment_polygon.shp")
        catchment_polygon = hyetograph.catchment_area_geometry_info(catchment_file_path)
        self.assertIsInstance(catchment_polygon, Polygon)


class RainfallSitesTest(unittest.TestCase):

    @staticmethod
    def open_file(filepath: str) -> str:
        file = pathlib.Path().cwd() / pathlib.Path(filepath)
        with open(file) as in_file:
            file_content = in_file.read()
            return file_content

    @classmethod
    @patch("src.dynamic_boundary_conditions.rainfall_sites.get_rainfall_sites_data")
    def setUpClass(cls, mock_sites_data):
        mock_sites_data.return_value = cls.open_file(r"tests/test_dynamic_boundary_conditions/data/rainfall_sites.txt")
        cls.sites = rainfall_sites.get_rainfall_sites_in_df()

    def test_rainfall_sites_in_df_correct_frame_type(self):
        self.assertIsInstance(self.sites, gpd.GeoDataFrame)

    def test_rainfall_sites_in_df_added_geom_column(self):
        column_name = self.sites.columns[-1]
        self.assertEqual(column_name, "geometry")

    def test_get_rainfall_sites_data_not_empty(self):
        sites_data = rainfall_sites.get_rainfall_sites_data()
        self.assertGreater(len(sites_data), 0)

    def test_get_rainfall_sites_data_correct_data_type(self):
        sites_data = rainfall_sites.get_rainfall_sites_data()
        self.assertIsInstance(sites_data, str)


if __name__ == "__main__":
    unittest.main()
