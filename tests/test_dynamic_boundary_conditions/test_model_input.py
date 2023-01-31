import unittest
import pathlib
from shapely.geometry import Polygon
import geopandas as gpd
import pandas as pd
from unittest.mock import patch

from src.dynamic_boundary_conditions import model_input


class ModelInputTest(unittest.TestCase):
    """Tests for model_input.py."""

    @staticmethod
    def get_catchment_polygon(filepath: str) -> Polygon:
        catchment_file = pathlib.Path(filepath)
        catchment = gpd.read_file(catchment_file)
        catchment = catchment.to_crs(4326)
        catchment_polygon = catchment["geometry"][0]
        return catchment_polygon

    @classmethod
    def setUpClass(cls):
        cls.selected_polygon = cls.get_catchment_polygon(
            r"tests/test_dynamic_boundary_conditions/data/selected_polygon.geojson")
        cls.sites_in_catchment = gpd.read_file(
            r"tests/test_dynamic_boundary_conditions/data/sites_in_catchment.geojson")
        cls.intersections = gpd.read_file(
            r"tests/test_dynamic_boundary_conditions/data/intersections.geojson")

    def test_sites_voronoi_intersect_catchment_in_catchment(self):
        intersections = model_input.sites_voronoi_intersect_catchment(self.sites_in_catchment, self.selected_polygon)
        self.assertTrue(intersections.within(self.selected_polygon.buffer(1 / 1e13)).unique())

    @patch("src.dynamic_boundary_conditions.model_input.sites_voronoi_intersect_catchment")
    def test_sites_coverage_in_catchment_correct_area_percent(self, mock_intersections):
        mock_intersections.return_value = self.intersections.copy()
        sites_coverage = model_input.sites_coverage_in_catchment(
            sites_in_catchment=gpd.GeoDataFrame(),
            catchment_polygon=Polygon())

        sites_area = (self.intersections.to_crs(3857).area / 1e6)
        sites_area_percent = sites_area / sites_area.sum()
        pd.testing.assert_series_equal(sites_area_percent, sites_coverage["area_percent"], check_names=False)
        self.assertEqual(1, sites_coverage["area_percent"].sum())
