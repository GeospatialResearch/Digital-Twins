import unittest
import geopandas as gpd
from shapely.geometry import Point
from unittest.mock import patch, MagicMock
from src.digitaltwin import get_data_using_geoapis


def run(layer_id):
    # Return a sample GeoDataFrame for testing
    data = {
        'Name': ['Feature 1', 'Feature 2'],
        'Value': [10, 20],
        'geometry': [Point(1, 3), Point(2, 4)]
    }
    return gpd.GeoDataFrame(data, geometry='geometry', crs='EPSG:4326')


class TestFetchVectorDataUsingGeoApis(unittest.TestCase):

    @patch('src.digitaltwin.get_data_using_geoapis.config.get_env_variable', MagicMock(return_value='test_api_key'))
    def test_fetch_vector_data_statsnz(self):
        # Test fetching vector data from StatsNZ
        result = get_data_using_geoapis.fetch_vector_data_using_geoapis("StatsNZ", 1)
        self.assertIsInstance(result, gpd.GeoDataFrame)
        # Add more assertions based on the expected behavior of the function

    @patch('src.digitaltwin.get_data_using_geoapis.config.get_env_variable', MagicMock(return_value='test_api_key'))
    def test_fetch_vector_data_linz(self):
        # Test fetching vector data from LINZ
        result = get_data_using_geoapis.fetch_vector_data_using_geoapis("LINZ", 2)
        self.assertIsInstance(result, gpd.GeoDataFrame)
        # Add more assertions based on the expected behavior of the function

    @patch('src.digitaltwin.get_data_using_geoapis.config.get_env_variable', MagicMock(return_value='test_api_key'))
    def test_fetch_vector_data_lris(self):
        # Test fetching vector data from LRIS
        result = get_data_using_geoapis.fetch_vector_data_using_geoapis("LRIS", 3)
        self.assertIsInstance(result, gpd.GeoDataFrame)
        # Add more assertions based on the expected behavior of the function

    @patch('src.digitaltwin.get_data_using_geoapis.config.get_env_variable', MagicMock(return_value='test_api_key'))
    def test_fetch_vector_data_mfe(self):
        # Test fetching vector data from MFE
        result = get_data_using_geoapis.fetch_vector_data_using_geoapis("MFE", 4)
        self.assertIsInstance(result, gpd.GeoDataFrame)
        # Add more assertions based on the expected behavior of the function

    def test_fetch_vector_data_unsupported_provider(self):
        # Test raising ValueError for an unsupported data provider
        with self.assertRaises(ValueError):
            get_data_using_geoapis.fetch_vector_data_using_geoapis("UnknownProvider", 1)


if __name__ == '__main__':
    unittest.main()
