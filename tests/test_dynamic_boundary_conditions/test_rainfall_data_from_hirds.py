import pathlib
import unittest
import math
from src.dynamic_boundary_conditions import rainfall_data_from_hirds


class TestRainfallDataFromHirds(unittest.TestCase):

    @staticmethod
    def open_file(filepath: str) -> str:
        file = pathlib.Path(filepath)
        with open(file) as in_file:
            file_content = in_file.read()
            return file_content

    @classmethod
    def setUpClass(cls):
        cls.rainfall_depth = TestRainfallDataFromHirds.open_file(
            r"tests\test_dynamic_boundary_conditions\data\rainfall_depth.txt")
        cls.rainfall_intensity = TestRainfallDataFromHirds.open_file(
            r"tests\test_dynamic_boundary_conditions\data\rainfall_intensity.txt")
        cls.depth_historical = TestRainfallDataFromHirds.open_file(
            r"tests\test_dynamic_boundary_conditions\data\depth_historical.txt")

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

    @staticmethod
    def layouts(layout_1, layout_2, start=None, end=None):
        layout_1 = layout_1[start:end]
        layout_2 = layout_2[start:end]
        layout_structures = [layout_1, layout_2]
        return layout_structures

    def test_get_layout_structure_of_data_expected_data_types(self):
        layout_structures = TestRainfallDataFromHirds.layouts(self.depth_layout, self.intensity_layout)
        for layout_structure in layout_structures:
            for block_structure in layout_structure:
                self.assertIsInstance(block_structure.skip_rows, int)
                self.assertIsInstance(block_structure.rcp, float)
                self.assertIsInstance(block_structure.time_period, (type(None), str))
                self.assertIsInstance(block_structure.category, str)

    def test_get_layout_structure_of_data_rcp_nan(self):
        layout_structures = TestRainfallDataFromHirds.layouts(self.depth_layout, self.intensity_layout, end=2)
        for layout_structure in layout_structures:
            for block_structure in layout_structure:
                self.assertTrue(math.isnan(block_structure.rcp))

    def test_get_layout_structure_of_data_rcp_not_nan(self):
        layout_structures = TestRainfallDataFromHirds.layouts(self.depth_layout, self.intensity_layout, start=2)
        for layout_structure in layout_structures:
            for block_structure in layout_structure:
                self.assertFalse(math.isnan(block_structure.rcp))

    def test_get_layout_structure_of_data_time_period_none(self):
        layout_structures = TestRainfallDataFromHirds.layouts(self.depth_layout, self.intensity_layout, end=2)
        for layout_structure in layout_structures:
            for block_structure in layout_structure:
                self.assertIsNone(block_structure.time_period)

    def test_get_layout_structure_of_data_time_period_not_none(self):
        layout_structures = TestRainfallDataFromHirds.layouts(self.depth_layout, self.intensity_layout, start=2)
        for layout_structure in layout_structures:
            for block_structure in layout_structure:
                self.assertIsNotNone(block_structure.time_period)

    def test_get_layout_structure_of_data_category_hist(self):
        layout_structures = TestRainfallDataFromHirds.layouts(self.depth_layout, self.intensity_layout, end=1)
        for layout_structure in layout_structures:
            for block_structure in layout_structure:
                self.assertIs(block_structure.category, "hist")

    def test_get_layout_structure_of_data_category_hist_stderr(self):
        layout_structures = TestRainfallDataFromHirds.layouts(self.depth_layout, self.intensity_layout, start=1, end=2)
        for layout_structure in layout_structures:
            for block_structure in layout_structure:
                self.assertIs(block_structure.category, "hist_stderr")

    def test_get_layout_structure_of_data_category_proj(self):
        layout_structures = TestRainfallDataFromHirds.layouts(self.depth_layout, self.intensity_layout, start=2)
        for layout_structure in layout_structures:
            for block_structure in layout_structure:
                self.assertIs(block_structure.category, "proj")


if __name__ == "__main__":
    unittest.main()

