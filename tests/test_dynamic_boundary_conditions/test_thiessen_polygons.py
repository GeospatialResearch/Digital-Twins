import unittest
import pathlib
import geopandas as gpd
from shapely.geometry import Polygon
from src.dynamic_boundary_conditions import thiessen_polygons


class ThiessenPolygonsTest(unittest.TestCase):
    """Tests for thiessen_polygons.py."""

    @staticmethod
    def get_nz_boundary_polygon(filepath: str) -> Polygon:
        """
        Get the New Zealand boundary geometry (polygon).

        Parameters
        ----------
        filepath
            The file path of the New Zealand boundary GeoJSON data file.
        """
        nz_boundary_file = pathlib.Path(filepath)
        nz_boundary = gpd.read_file(nz_boundary_file)
        nz_boundary = nz_boundary.to_crs(4326)
        nz_boundary_polygon = nz_boundary["geometry"][0]
        return nz_boundary_polygon

    @classmethod
    def setUpClass(cls):
        cls.nz_boundary_polygon = cls.get_nz_boundary_polygon(
            r"tests/test_dynamic_boundary_conditions/data/nz_boundary.geojson")
        cls.sites_in_nz = gpd.read_file(r"tests/test_dynamic_boundary_conditions/data/sites_in_nz.geojson")

    def test_thiessen_polygons_calculator_area_of_interest_empty(self):
        empty_area_of_interest = Polygon()
        with self.assertRaises(ValueError) as context:
            thiessen_polygons.thiessen_polygons_calculator(empty_area_of_interest, self.sites_in_nz)
        self.assertEqual("No data available for area_of_interest passed as argument", str(context.exception))

    def test_thiessen_polygons_calculator_sites_in_aoi_empty(self):
        empty_sites_in_aoi = gpd.GeoDataFrame()
        with self.assertRaises(ValueError) as context:
            thiessen_polygons.thiessen_polygons_calculator(self.nz_boundary_polygon, empty_sites_in_aoi)
        self.assertEqual("No data available for sites_in_aoi passed as argument", str(context.exception))

    def test_thiessen_polygons_calculator_correct_voronoi_number(self):
        rainfall_sites_voronoi = thiessen_polygons.thiessen_polygons_calculator(
            self.nz_boundary_polygon, self.sites_in_nz)
        self.assertEqual(len(self.sites_in_nz), len(rainfall_sites_voronoi))


if __name__ == "__main__":
    unittest.main()
