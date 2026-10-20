"""Tests for the fetch_arcgis_rest_data provider-registry wrapper in arcgis_rest_api.py"""
import unittest
from unittest import mock

import geopandas as gpd
import shapely

from eddie.digitaltwin import arcgis_rest_api


class FetchArcgisRestDataTest(unittest.TestCase):
    """Tests for fetch_arcgis_rest_data, the (layer_id, bbox, crs) -> GeoDataFrame registry provider."""

    @mock.patch.object(arcgis_rest_api, "fetch_arcgis_rest_api_data")
    def test_no_bbox_fetches_all_data_with_output_sr(self, fetch):
        arcgis_rest_api.fetch_arcgis_rest_data("https://example.com/FeatureServer/0", None, 4326)
        fetch.assert_called_once_with("https://example.com/FeatureServer/0", output_sr=4326)

    @mock.patch.object(arcgis_rest_api, "fetch_arcgis_rest_api_data")
    def test_bbox_fetches_with_area_of_interest(self, fetch):
        bbox = gpd.GeoDataFrame(geometry=[shapely.box(0, 0, 1, 1)], crs=4326)
        arcgis_rest_api.fetch_arcgis_rest_data("https://example.com/FeatureServer/0", bbox, 4326)
        fetch.assert_called_once_with("https://example.com/FeatureServer/0", area_of_interest=bbox)

    @mock.patch.object(arcgis_rest_api, "fetch_arcgis_rest_api_data")
    def test_returns_fetcher_result(self, fetch):
        expected = gpd.GeoDataFrame({"id": [1]}, geometry=[shapely.Point(0, 0)], crs=4326)
        fetch.return_value = expected
        result = arcgis_rest_api.fetch_arcgis_rest_data("https://example.com/FeatureServer/0", None, 4326)
        self.assertIs(result, expected)


if __name__ == "__main__":
    unittest.main()
