import unittest
import pathlib
from shapely.geometry import Polygon
from src.dynamic_boundary_conditions import main_rainfall


class HyetographTest(unittest.TestCase):
    """Tests for hyetograph.py."""

    def test_catchment_area_geometry_info_correct_type(self):
        """Test to ensure that a shapely geometry polygon is extracted from the catchment file."""
        catchment_file_path = pathlib.Path(r"tests/test_dynamic_boundary_conditions/data/catchment_polygon.shp")
        catchment_polygon = main_rainfall.catchment_area_geometry_info(catchment_file_path)
        self.assertIsInstance(catchment_polygon, Polygon)


if __name__ == "__main__":
    unittest.main()
