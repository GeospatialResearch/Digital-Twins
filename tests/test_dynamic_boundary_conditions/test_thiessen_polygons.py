import unittest
import pathlib

import geopandas as gpd
from shapely.geometry import Polygon

from src.dynamic_boundary_conditions import thiessen_polygons


class ThiessenPolygonsTest(unittest.TestCase):
    """Tests for thiessen_polygons.py."""

    @staticmethod
    def get_nz_boundary(nz_boundary_file: str, to_crs: int = 4326) -> gpd.GeoDataFrame:
        """
        Read New Zealand boundary data from a GeoJSON file and convert it to the desired coordinate reference system.

        Parameters
        ----------
        nz_boundary_file : str
            The file path to the GeoJSON file containing the New Zealand boundary data.
        to_crs : int, optional
            Coordinate Reference System (CRS) code to convert the New Zealand boundary to. Default is 4326.

        Returns
        -------
        gpd.GeoDataFrame
            A GeoDataFrame representing the boundary of New Zealand in the specified CRS.
        """
        # Load the New Zealand boundary data from the GeoJSON file
        nz_boundary = gpd.GeoDataFrame.from_file(nz_boundary_file)
        # Convert the New Zealand boundary data to the desired CRS
        nz_boundary_crs_transformed = nz_boundary.to_crs(to_crs)
        return nz_boundary_crs_transformed

    @classmethod
    def setUpClass(cls):
        """Get the New Zealand boundary polygon and rainfall sites data."""
        cls.nz_boundary = cls.get_nz_boundary(
            r"tests/test_dynamic_boundary_conditions/data/nz_boundary.geojson")
        cls.sites_in_nz = gpd.read_file(r"tests/test_dynamic_boundary_conditions/data/sites_in_nz.geojson")

    def test_thiessen_polygons_calculator_area_of_interest_empty(self):
        """Test to ensure ValueError is raised when 'area_of_interest' is empty."""
        empty_area_of_interest = gpd.GeoDataFrame()
        with self.assertRaises(ValueError) as context:
            thiessen_polygons.thiessen_polygons_calculator(empty_area_of_interest, self.sites_in_nz)
        self.assertEqual("No data available for 'area_of_interest' passed as argument.", str(context.exception))

    def test_thiessen_polygons_calculator_sites_in_aoi_empty(self):
        """Test to ensure ValueError is raised when 'sites_in_aoi' is empty."""
        empty_sites_in_aoi = gpd.GeoDataFrame()
        with self.assertRaises(ValueError) as context:
            thiessen_polygons.thiessen_polygons_calculator(self.nz_boundary, empty_sites_in_aoi)
        self.assertEqual("No data available for 'sites_in_aoi' passed as argument.", str(context.exception))

    def test_thiessen_polygons_calculator_correct_voronoi_number(self):
        """Test to ensure thiessen polygons are created for all rainfall sites within New Zealand."""
        rainfall_sites_voronoi = thiessen_polygons.thiessen_polygons_calculator(
            self.nz_boundary, self.sites_in_nz)
        self.assertEqual(len(self.sites_in_nz), len(rainfall_sites_voronoi))

    def test_thiessen_polygons_calculator_correct_area_in_km2(self):
        """Test to ensure correct area calculation for all rainfall sites thiessen polygons."""
        nz_boundary_area = float(self.nz_boundary.to_crs(3857).area / 1e6)
        rainfall_sites_voronoi = thiessen_polygons.thiessen_polygons_calculator(
            self.nz_boundary, self.sites_in_nz)
        voronoi_area_sum = sum(rainfall_sites_voronoi["area_in_km2"])
        self.assertAlmostEqual(nz_boundary_area, voronoi_area_sum, places=2)


if __name__ == "__main__":
    unittest.main()
