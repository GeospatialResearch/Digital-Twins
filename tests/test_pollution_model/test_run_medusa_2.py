"""Tests for run_medusa_2.py."""
import unittest
import numpy as np

from otakaro.pollution_model.run_medusa_2 import (MedusaRainfallEvent, compute_tss_roof_road,
                                                  total_metal_load_roof, dissolved_metal_load,
                                                  total_metal_load_road_carpark,
                                                  run_medusa_model_for_surface_geometries, SurfaceType)

import geopandas as gpd
import pandas as pd


class RunMedusaTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up arguments used for testing."""
        # Realistic surface area of a single building
        cls.surface_area = 173
        # Realistic rainfall event for Christchurch, New Zealand
        cls.rainfall_event = MedusaRainfallEvent(1.45833333333333, 0.5, 2, 6.5)
        # A small sample of buildings in Christchurch, New Zealand
        cls.test_buildings_gdf = gpd.read_file("tests/test_pollution_model/data/test_buildings.geojson")

    # Test Roof
    def test_tss_roof_matches_excel(self):
        """Tests that the TSS implementation matches sample data from MEDUSA authors."""
        tss_roof_result = np.round(compute_tss_roof_road(
            self.surface_area, self.rainfall_event, SurfaceType.COLORSTEEL), 3)
        excel_tss_roof_result = 582.040
        self.assertEqual(tss_roof_result, excel_tss_roof_result)

    def test_copper_zinc_roof_matches_excel(self):
        """Tests that roof TCu and TZn implementation matches sample data from MEDUSA authors."""
        copper_roof_result, zinc_roof_result = np.round(total_metal_load_roof(
            self.surface_area, self.rainfall_event, SurfaceType.METAL_TILE), 3)
        excel_copper_roof_result = 0.701
        excel_zinc_roof_result = 103.148
        self.assertEqual(copper_roof_result, excel_copper_roof_result)
        self.assertEqual(zinc_roof_result, excel_zinc_roof_result)

    def test_dissolve_copper_zinc_roof_matches_excel(self):
        """Tests that roof DCu and DZn implementation matches sample data from MEDUSA authors."""
        surface_type = SurfaceType.NON_METAL
        copper_roof_result, zinc_roof_result = total_metal_load_roof(
            self.surface_area, self.rainfall_event, surface_type)
        dissolve_copper_roof_result, dissolve_zinc_roof_result = np.round(dissolved_metal_load(
            copper_roof_result, zinc_roof_result, surface_type), 3)
        excel_dissolve_copper_roof_result = 0.54
        excel_dissolve_zinc_roof_result = 9.594
        self.assertEqual(dissolve_copper_roof_result, excel_dissolve_copper_roof_result)
        self.assertEqual(dissolve_zinc_roof_result, excel_dissolve_zinc_roof_result)

    def test_tss_road_matches_excel(self):
        """Tests that road TSS implementation matches sample data from MEDUSA authors."""
        tss_road_result = np.round(compute_tss_roof_road(
            self.surface_area, self.rainfall_event, SurfaceType.ASPHALT_ROAD), 3)
        excel_road_tss_result = 6980.284
        self.assertEqual(tss_road_result, excel_road_tss_result)

    def test_copper_zinc_road_matches_excel(self):
        """Tests that road TCu and TZn implementation matches sample data from MEDUSA authors."""
        tss_road_result = compute_tss_roof_road(
            self.surface_area, self.rainfall_event, SurfaceType.ASPHALT_ROAD)
        copper_road_result, zinc_road_result = np.round(total_metal_load_road_carpark(
            tss_road_result), 3)
        excel_copper_road_result = 3078.305
        excel_zinc_road_result = 13681.356
        self.assertEqual(copper_road_result, excel_copper_road_result)
        self.assertEqual(zinc_road_result, excel_zinc_road_result)

    def test_dissolve_copper_zinc_road_matches_excel(self):
        """Tests that road DCu and DZn implementation matches sample data from MEDUSA authors."""
        tss_road_result = compute_tss_roof_road(
            self.surface_area, self.rainfall_event, SurfaceType.ASPHALT_ROAD)
        copper_road_result, zinc_road_result = total_metal_load_road_carpark(
            tss_road_result)
        dissolve_copper_road_result, dissolve_zinc_road_result = np.round(dissolved_metal_load(
            copper_road_result, zinc_road_result, SurfaceType.ASPHALT_ROAD), 3)
        excel_dissolve_copper_road_result = 861.925
        excel_dissolve_zinc_road_result = 5882.983
        self.assertEqual(dissolve_copper_road_result, excel_dissolve_copper_road_result)
        self.assertEqual(dissolve_zinc_road_result, excel_dissolve_zinc_road_result)

    def test_run_medusa_model(self):
        """Tests a variety of building surfaces using the full MEDUSA implementation functions."""
        # Run through each building and calculations
        all_buildings = run_medusa_model_for_surface_geometries(
            self.test_buildings_gdf, self.rainfall_event
        )
        all_buildings = all_buildings.drop('geometry', axis=1)
        # Get columns need testing
        all_buildings_testing = np.round(all_buildings[all_buildings.columns[2:]], 4)
        excel_all_buildings_testing = pd.DataFrame(
            data={
                'total_suspended_solids': [582.3130, 380.7506, 57.9798, 321.3461, 553.3733],
                'total_copper': [0.7014, 0.4586, 0.0698, 0.3870, 0.4883],
                'total_zinc': [103.1962, 67.4758, 10.2750, 56.9482, 9.9739],
                'dissolved_copper': [0.3507, 0.2293, 0.0349, 0.1935, 0.3760],
                'dissolved_zinc': [44.3744, 29.0146, 4.4183, 24.4877, 6.6825]
            }
        )
        pd.testing.assert_frame_equal(all_buildings_testing, excel_all_buildings_testing)


if __name__ == '__main__':
    unittest.main()
