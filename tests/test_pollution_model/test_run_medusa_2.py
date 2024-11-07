import unittest
import numpy as np

from src.pollution_model.run_medusa_2 import MedusaRainfallEvent, compute_tss_roof_road


class RunMedusaTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up arguments used for testing."""
        cls.surface_area = 173
        cls.rainfall_event = MedusaRainfallEvent(1.45833333333333, 0.5, 2, 6.5)

    def test_tss_roof_matches_excel(self):
        tss_roof_result = np.round(compute_tss_roof_road(
            self.surface_area,
            self.rainfall_event,
            'ColourSteel'
        ), 2)
        excel_roof_tss_result = 582.04
        self.assertEquals(tss_roof_result, excel_roof_tss_result)

    def test_tss_road_matches_excel(self):
        tss_road_result = np.round(compute_tss_roof_road(
            self.surface_area,
            self.rainfall_event,
            'AsphaltRoad'
        ), 2)
        excel_road_tss_result = 6980.28
        self.assertEquals(tss_road_result, excel_road_tss_result)

    def test_fail(self):
        # todo fill in more test case methods for each function
        assert False


if __name__ == '__main__':
    unittest.main()
