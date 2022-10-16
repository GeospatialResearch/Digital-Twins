import pathlib
import unittest
import math
from src.dynamic_boundary_conditions import rainfall_data_from_hirds


def open_file(filepath: str) -> str:
    file = pathlib.Path(filepath)
    with open(file) as in_file:
        file_content = in_file.read()
        return file_content


class TestRainfallDataFromHirds(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rainfall_depth = open_file(r"tests\test_dynamic_boundary_conditions\data\rainfall_depth.txt")
        cls.rainfall_intensity = open_file(r"tests\test_dynamic_boundary_conditions\data\rainfall_intensity.txt")
        cls.depth_historical = open_file(r"tests\test_dynamic_boundary_conditions\data\depth_historical.txt")

        cls.depth_layout = rainfall_data_from_hirds.get_layout_structure_of_data(cls.rainfall_depth)
        cls.intensity_layout = rainfall_data_from_hirds.get_layout_structure_of_data(cls.rainfall_intensity)
        cls.depth_hist_layout = rainfall_data_from_hirds.get_layout_structure_of_data(cls.depth_historical)

    def test_get_data_from_hirds_not_empty(self):
        example_site_id = "323605"
        depth_data = rainfall_data_from_hirds.get_data_from_hirds(example_site_id, idf=False)
        intensity_data = rainfall_data_from_hirds.get_data_from_hirds(example_site_id, idf=True)
        self.assertGreater(len(depth_data), 0)
        self.assertGreater(len(intensity_data), 0)

    def test_get_layout_structure_of_data_expected_blocks(self):
        self.assertEqual(len(self.depth_layout), 10)
        self.assertEqual(len(self.intensity_layout), 10)
        self.assertEqual(len(self.depth_hist_layout), 1)

    def test_get_layout_structure_of_data_expected_data_types(self):
        layouts = [self.depth_layout, self.intensity_layout]
        for layout_structure in layouts:
            for block_structure in layout_structure:
                self.assertIsInstance(block_structure.skip_rows, int)
                self.assertIsInstance(block_structure.rcp, float)
                self.assertIsInstance(block_structure.time_period, (type(None), str))
                self.assertIsInstance(block_structure.category, str)

    def test_get_layout_structure_of_data_rcp_nan(self):
        self.assertTrue(math.isnan(self.depth_layout[0].rcp))
        self.assertTrue(math.isnan(self.depth_layout[1].rcp))
        self.assertTrue(math.isnan(self.intensity_layout[0].rcp))
        self.assertTrue(math.isnan(self.intensity_layout[1].rcp))

    def test_get_layout_structure_of_data_rcp_not_nan(self):
        self.assertFalse(math.isnan(self.depth_layout[2].rcp))
        self.assertFalse(math.isnan(self.depth_layout[-1].rcp))
        self.assertFalse(math.isnan(self.intensity_layout[2].rcp))
        self.assertFalse(math.isnan(self.intensity_layout[-1].rcp))

    def test_get_layout_structure_of_data_time_period_none(self):
        self.assertIsNone(self.depth_layout[0].time_period)
        self.assertIsNone(self.depth_layout[1].time_period)
        self.assertIsNone(self.intensity_layout[0].time_period)
        self.assertIsNone(self.intensity_layout[1].time_period)

    def test_get_layout_structure_of_data_time_period_not_none(self):
        self.assertIsNotNone(self.depth_layout[2].time_period)
        self.assertIsNotNone(self.depth_layout[-1].time_period)
        self.assertIsNotNone(self.intensity_layout[2].time_period)
        self.assertIsNotNone(self.intensity_layout[-1].time_period)


if __name__ == "__main__":
    unittest.main()

