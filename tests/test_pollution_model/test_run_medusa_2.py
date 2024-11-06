import unittest

from src.pollution_model.run_medusa_2 import MedusaRainfallEvent


class RunMedusaTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up arguments used for testing."""
        cls.surface_area = 10.66 # todo change this to a realistic value
        cls.rainfall_event = MedusaRainfallEvent(1, 1, 1, 1) # change this to realistic

    def test_tss_matches_excel(self):
        tss_result = None  # todo
        excel_tss_result = None # fill in this
        self.assertEquals(tss_result, excel_tss_result)

    def test_fail(self):
        # todo fill in more test case methods for each function
        assert False


if __name__ == '__main__':
    unittest.main()
