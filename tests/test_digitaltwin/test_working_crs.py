"""Tests for working_crs.py"""
import unittest
from unittest import mock

import geopandas as gpd
import shapely

from eddie.config import EnvVariable
from eddie.digitaltwin.working_crs import resolve_working_crs, to_working_crs_rectangle


def aoi(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> gpd.GeoDataFrame:
    """Build a rectangular WGS84 area of interest."""
    return gpd.GeoDataFrame(index=[0], crs=4326, geometry=[shapely.box(min_lon, min_lat, max_lon, max_lat)])


CHRISTCHURCH = aoi(172.5, -43.6, 172.7, -43.4)


@mock.patch.object(EnvVariable, "WORKING_CRS", None)
class ResolveWorkingCrsTest(unittest.TestCase):
    """Tests the config -> derived from area of interest -> EPSG:4326 order."""

    def test_config_wins_over_area(self):
        with mock.patch.object(EnvVariable, "WORKING_CRS", "EPSG:2193"):
            self.assertEqual(resolve_working_crs(CHRISTCHURCH), 2193)

    def test_config_accepts_bare_code(self):
        with mock.patch.object(EnvVariable, "WORKING_CRS", "3031"):
            self.assertEqual(resolve_working_crs(), 3031)

    def test_config_without_epsg_code_raises(self):
        with mock.patch.object(EnvVariable, "WORKING_CRS", "+proj=tmerc +lon_0=101.3 +ellps=GRS80"):
            with self.assertRaises(ValueError):
                resolve_working_crs()

    def test_utm_zone_of_area(self):
        self.assertEqual(resolve_working_crs(CHRISTCHURCH), 32759)
        self.assertEqual(resolve_working_crs(aoi(-0.2, 51.4, 0.1, 51.6)), 32630)

    def test_area_in_another_crs(self):
        self.assertEqual(resolve_working_crs(CHRISTCHURCH.to_crs(3857)), 32759)

    def test_polar_areas(self):
        self.assertEqual(resolve_working_crs(aoi(166.0, -78.0, 167.0, -77.0)), 3031)
        self.assertEqual(resolve_working_crs(aoi(-50.0, 70.0, -49.0, 71.0)), 3413)

    def test_fallback_without_area(self):
        self.assertEqual(resolve_working_crs(), 4326)
        self.assertEqual(resolve_working_crs(gpd.GeoDataFrame(geometry=[], crs=4326)), 4326)


def triangle(lon: float, lat: float, size: float) -> gpd.GeoDataFrame:
    """Build a non-rectangular WGS84 area of interest, so its bounding rectangle differs from it."""
    return gpd.GeoDataFrame(index=[0], crs=4326, geometry=[
        shapely.Polygon([(lon, lat), (lon + size, lat), (lon + size / 2, lat + size)])])


@mock.patch.object(EnvVariable, "WORKING_CRS", None)
class ToWorkingCrsRectangleTest(unittest.TestCase):
    """Tests for to_working_crs_rectangle."""

    def test_rectangle_in_working_crs(self):
        triangle = gpd.GeoDataFrame(index=[0], crs=4326,
                                    geometry=[shapely.Polygon([(172.5, -43.6), (172.7, -43.6), (172.6, -43.4)])])
        rectangle = to_working_crs_rectangle(triangle)
        self.assertEqual(rectangle.crs.to_epsg(), 32759)
        geometry = rectangle.geometry[0]
        self.assertAlmostEqual(geometry.area, geometry.envelope.area)
        self.assertTrue(geometry.contains(triangle.to_crs(32759).geometry[0]))

    def test_rectangle_in_configured_2193(self):
        christchurch = triangle(172.5, -43.6, 0.2)
        with mock.patch.object(EnvVariable, "WORKING_CRS", "EPSG:2193"):
            rectangle = to_working_crs_rectangle(christchurch)
        self.assertEqual(rectangle.crs.to_epsg(), 2193)
        expected = shapely.box(*christchurch.to_crs(2193).total_bounds)
        self.assertTrue(rectangle.geometry[0].equals_exact(expected, 1e-6))

    def test_rectangle_in_3031_for_antarctic_area(self):
        ross_island = triangle(166.0, -78.0, 1.0)
        rectangle = to_working_crs_rectangle(ross_island)
        self.assertEqual(rectangle.crs.to_epsg(), 3031)
        geometry = rectangle.geometry[0]
        self.assertAlmostEqual(geometry.area, geometry.envelope.area)
        self.assertTrue(geometry.contains(ross_island.to_crs(3031).geometry[0]))

    def test_multi_row_area_becomes_one_rectangle(self):
        two_boxes = gpd.GeoDataFrame(crs=4326, geometry=[shapely.box(172.5, -43.6, 172.55, -43.55),
                                                          shapely.box(172.65, -43.45, 172.7, -43.4)])
        rectangle = to_working_crs_rectangle(two_boxes)
        self.assertEqual(len(rectangle), 1)
        expected = shapely.box(*two_boxes.to_crs(32759).total_bounds)
        self.assertTrue(rectangle.geometry[0].equals_exact(expected, 1e-6))


if __name__ == "__main__":
    unittest.main()