"""Tests for get_data_using_geoapis.py"""
import unittest
from unittest import mock

import geopandas as gpd
import shapely

from eddie.digitaltwin import get_data_using_geoapis

AOI_4326 = gpd.GeoDataFrame(geometry=[shapely.box(172.62, -43.54, 172.65, -43.52)], crs=4326)


@mock.patch.object(get_data_using_geoapis, "StatsNz")
class FetchCrsTest(unittest.TestCase):
    """Tests that data is fetched in the requested CRS when geoapis can query in it, else in EPSG:4326."""

    def fetch(self, stats_nz: mock.Mock, crs: int, fetched: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        stats_nz.return_value.run.return_value = fetched
        return get_data_using_geoapis.fetch_vector_data_using_geoapis(
            "StatsNZ", 1, crs, bounding_polygon=AOI_4326.to_crs(crs))

    def test_north_east_crs_fetched_directly(self, stats_nz):
        fetched = gpd.GeoDataFrame({"ID": [1]}, crs=2193, geometry=[shapely.Point(1570000, 5180000)])
        result = self.fetch(stats_nz, 2193, fetched)
        self.assertEqual(stats_nz.call_args.kwargs["crs"], 2193)
        self.assertEqual(stats_nz.call_args.kwargs["bounding_polygon"].crs.to_epsg(), 2193)
        self.assertEqual(result.crs.to_epsg(), 2193)
        self.assertEqual(list(result.columns), ["id", "geometry"])

    def test_other_crs_fetched_in_4326(self, stats_nz):
        for crs in (32759, 3031):
            fetched = gpd.GeoDataFrame({"ID": [1]}, crs=4326, geometry=[shapely.Point(172.63, -43.53)])
            result = self.fetch(stats_nz, crs, fetched)
            self.assertEqual(stats_nz.call_args.kwargs["crs"], 4326)
            self.assertEqual(stats_nz.call_args.kwargs["bounding_polygon"].crs.to_epsg(), 4326)
            self.assertEqual(result.crs.to_epsg(), crs)


if __name__ == "__main__":
    unittest.main()