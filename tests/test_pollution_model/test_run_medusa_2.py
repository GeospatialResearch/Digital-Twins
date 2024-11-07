import unittest
import numpy as np

from src.pollution_model.run_medusa_2 import (MedusaRainfallEvent, compute_tss_roof_road,
                                              total_metal_load_roof, dissolved_metal_load,
                                              total_metal_load_road_carpark)


class RunMedusaTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up arguments used for testing."""
        cls.surface_area = 173
        cls.rainfall_event = MedusaRainfallEvent(1.45833333333333, 0.5, 2, 6.5)

    # Test Roof
    def test_tss_roof_matches_excel(self):
        tss_roof_result = np.round(compute_tss_roof_road(
            self.surface_area, self.rainfall_event, 'ColourSteel'), 3)
        excel_tss_roof_result = 582.040
        self.assertEquals(tss_roof_result, excel_tss_roof_result)

    def test_copper_zinc_roof_matches_excel(self):
        copper_roof_result, zinc_roof_result = np.round(total_metal_load_roof(
            self.surface_area, self.rainfall_event, 'ColourSteel'), 3)
        excel_copper_roof_result = 0.701
        excel_zinc_roof_result = 103.148
        self.assertEquals(copper_roof_result, excel_copper_roof_result)
        self.assertEquals(zinc_roof_result, excel_zinc_roof_result)

    def test_dissolve_copper_zinc_roof_matches_excel(self):
        copper_roof_result, zinc_roof_result = total_metal_load_roof(
            self.surface_area, self.rainfall_event, 'ColourSteel')
        dissolve_copper_roof_result, dissolve_zinc_roof_result = np.round(dissolved_metal_load(
            copper_roof_result, zinc_roof_result, 'ColourSteel'), 3)
        excel_dissolve_copper_roof_result = 0.351
        excel_dissolve_zinc_roof_result = 44.354
        self.assertEquals(dissolve_copper_roof_result, excel_dissolve_copper_roof_result)
        self.assertEquals(dissolve_zinc_roof_result, excel_dissolve_zinc_roof_result)

    # Test Road
    def test_tss_road_matches_excel(self):
        tss_road_result = np.round(compute_tss_roof_road(
            self.surface_area, self.rainfall_event,'AsphaltRoad'), 3)
        excel_road_tss_result = 6980.284
        self.assertEquals(tss_road_result, excel_road_tss_result)

    def test_copper_zinc_road_matches_excel(self):
        tss_road_result = compute_tss_roof_road(
            self.surface_area, self.rainfall_event, 'AsphaltRoad')
        copper_road_result, zinc_road_result = np.round(total_metal_load_road_carpark(
            tss_road_result), 3)
        excel_copper_road_result = 3078.305
        excel_zinc_road_result = 13681.356
        self.assertEquals(copper_road_result, excel_copper_road_result)
        self.assertEquals(zinc_road_result, excel_zinc_road_result)

    def test_dissolve_copper_zinc_road_matches_excel(self):
        tss_road_result = compute_tss_roof_road(
            self.surface_area, self.rainfall_event, 'AsphaltRoad')
        copper_road_result, zinc_road_result = total_metal_load_road_carpark(
            tss_road_result)
        dissolve_copper_road_result, dissolve_zinc_road_result = np.round(dissolved_metal_load(
            copper_road_result, zinc_road_result, 'AsphaltRoad'), 3)
        excel_dissolve_copper_road_result = 861.925
        excel_dissolve_zinc_road_result = 5882.983
        self.assertEquals(dissolve_copper_road_result, excel_dissolve_copper_road_result)
        self.assertEquals(dissolve_zinc_road_result, excel_dissolve_zinc_road_result)

    def test_fail(self):
        # todo fill in more test case methods for each function
        assert False

if __name__ == '__main__':
    unittest.main()
