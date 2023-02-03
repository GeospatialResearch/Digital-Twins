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
        """Get the New Zealand boundary polygon and rainfall sites data."""
        cls.nz_boundary_polygon = cls.get_nz_boundary_polygon(
            r"tests/test_dynamic_boundary_conditions/data/nz_boundary.geojson")
        cls.sites_in_nz = gpd.read_file(r"tests/test_dynamic_boundary_conditions/data/sites_in_nz.geojson")

    def test_thiessen_polygons_calculator_area_of_interest_empty(self):
        """Test to ensure ValueError is raised when 'area_of_interest' is empty."""
        empty_area_of_interest = Polygon()
        with self.assertRaises(ValueError) as context:
            thiessen_polygons.thiessen_polygons_calculator(empty_area_of_interest, self.sites_in_nz)
        self.assertEqual("No data available for area_of_interest passed as argument", str(context.exception))

    def test_thiessen_polygons_calculator_sites_in_aoi_empty(self):
        """Test to ensure ValueError is raised when 'sites_in_aoi' is empty."""
        empty_sites_in_aoi = gpd.GeoDataFrame()
        with self.assertRaises(ValueError) as context:
            thiessen_polygons.thiessen_polygons_calculator(self.nz_boundary_polygon, empty_sites_in_aoi)
        self.assertEqual("No data available for sites_in_aoi passed as argument", str(context.exception))

    def test_thiessen_polygons_calculator_correct_voronoi_number(self):
        """Test to ensure thiessen polygons are created for all rainfall sites within New Zealand."""
        rainfall_sites_voronoi = thiessen_polygons.thiessen_polygons_calculator(
            self.nz_boundary_polygon, self.sites_in_nz)
        self.assertEqual(len(self.sites_in_nz), len(rainfall_sites_voronoi))

    def test_thiessen_polygons_calculator_correct_area_in_km2(self):
        """Test to ensure correct area calculation for all rainfall sites thiessen polygons."""
        nz_boundary = gpd.GeoDataFrame(index=[0], crs="EPSG:4326", geometry=[self.nz_boundary_polygon])
        nz_boundary_area = float(nz_boundary.to_crs(3857).area / 1e6)
        rainfall_sites_voronoi = thiessen_polygons.thiessen_polygons_calculator(
            self.nz_boundary_polygon, self.sites_in_nz)
        voronoi_area_sum = sum(rainfall_sites_voronoi["area_in_km2"])
        self.assertAlmostEqual(nz_boundary_area, voronoi_area_sum, places=2)


if __name__ == "__main__":
    unittest.main()
