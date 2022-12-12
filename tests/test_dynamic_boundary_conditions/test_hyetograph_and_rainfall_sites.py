import unittest
from unittest.mock import patch
import pathlib
from shapely.geometry import Polygon
import geopandas as gpd
from src.dynamic_boundary_conditions import main_rainfall, rainfall_sites


class HyetographTest(unittest.TestCase):
    """Tests for hyetograph.py."""

    def test_catchment_area_geometry_info_correct_type(self):
        """Test to ensure that a shapely geometry polygon is extracted from the catchment file."""
        catchment_file_path = pathlib.Path(r"tests/test_dynamic_boundary_conditions/data/catchment_polygon.shp")
        catchment_polygon = main_rainfall.catchment_area_geometry_info(catchment_file_path)
        self.assertIsInstance(catchment_polygon, Polygon)


class RainfallSitesTest(unittest.TestCase):
    """Tests for rainfall_sites.py."""

    @staticmethod
    def open_file(filepath: str) -> str:
        """
        Read the content of a text data file.

        Parameters
        ----------
        filepath : str
            The file path of the text data file.
        """
        data_file = pathlib.Path(filepath)
        with open(data_file) as in_file:
            file_content = in_file.read()
            return file_content

    @classmethod
    @patch("src.dynamic_boundary_conditions.rainfall_sites.get_rainfall_sites_data")
    def setUpClass(cls, mock_sites_data):
        """Get rainfall sites data and convert it to tabular format."""
        mock_sites_data.return_value = cls.open_file(r"tests/test_dynamic_boundary_conditions/data/rainfall_sites.txt")
        cls.sites = rainfall_sites.get_rainfall_sites_in_df()

    def test_rainfall_sites_in_df_correct_frame_type(self):
        """Test to ensure tabular data is returned in GeoDataFrame format."""
        self.assertIsInstance(self.sites, gpd.GeoDataFrame)

    def test_rainfall_sites_in_df_added_geom_column(self):
        """Test to ensure the 'geometry' column was added."""
        column_name = self.sites.columns[-1]
        self.assertEqual(column_name, "geometry")

    def test_get_rainfall_sites_data_not_empty(self):
        """Test to ensure that the rainfall sites data fetched from the HIRDS website is not empty."""
        sites_data = rainfall_sites.get_rainfall_sites_data()
        self.assertGreater(len(sites_data), 0)


if __name__ == "__main__":
    unittest.main()
