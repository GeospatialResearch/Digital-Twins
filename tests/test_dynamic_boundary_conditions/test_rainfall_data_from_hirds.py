import pathlib
import unittest
import math
from typing import List
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
            r"tests/test_dynamic_boundary_conditions/data/rainfall_depth.txt")
        cls.rainfall_intensity = TestRainfallDataFromHirds.open_file(
            r"tests/test_dynamic_boundary_conditions/data/rainfall_intensity.txt")
        cls.depth_historical = TestRainfallDataFromHirds.open_file(
            r"tests/test_dynamic_boundary_conditions/data/depth_historical.txt")

        cls.depth_layout = rainfall_data_from_hirds.get_layout_structure_of_data(cls.rainfall_depth)
        cls.intensity_layout = rainfall_data_from_hirds.get_layout_structure_of_data(cls.rainfall_intensity)
        cls.depth_hist_layout = rainfall_data_from_hirds.get_layout_structure_of_data(cls.depth_historical)

        cls.example_site_id = "323605"

    def test_get_data_from_hirds_not_empty(self):
        depth_data = rainfall_data_from_hirds.get_data_from_hirds(self.example_site_id, idf=False)
        intensity_data = rainfall_data_from_hirds.get_data_from_hirds(self.example_site_id, idf=True)
        self.assertGreater(len(depth_data), 0)
        self.assertGreater(len(intensity_data), 0)

    def test_get_layout_structure_of_data_expected_blocks(self):
        self.assertEqual(len(self.depth_layout), 10)
        self.assertEqual(len(self.intensity_layout), 10)
        self.assertEqual(len(self.depth_hist_layout), 1)

    @staticmethod
    def get_block_structures(
            layout_1: List[rainfall_data_from_hirds.BlockStructure],
            layout_2: List[rainfall_data_from_hirds.BlockStructure],
            start=None,
            end=None) -> List[rainfall_data_from_hirds.BlockStructure]:
        layout_structures = (layout_1[start:end], layout_2[start:end])
        block_structures = []
        for layout_structure in layout_structures:
            for block_structure in layout_structure:
                block_structures.append(block_structure)
        return block_structures

    def test_get_layout_structure_of_data_expected_data_types(self):
        block_structures = TestRainfallDataFromHirds.get_block_structures(self.depth_layout, self.intensity_layout)
        for block_structure in block_structures:
            self.assertIsInstance(block_structure.skip_rows, int)
            self.assertIsInstance(block_structure.rcp, float)
            self.assertIsInstance(block_structure.time_period, (type(None), str))
            self.assertIsInstance(block_structure.category, str)

    def test_get_layout_structure_of_data_rcp_nan(self):
        block_structures = TestRainfallDataFromHirds.get_block_structures(
            self.depth_layout, self.intensity_layout, end=2)
        for block_structure in block_structures:
            self.assertTrue(math.isnan(block_structure.rcp))

    def test_get_layout_structure_of_data_rcp_not_nan(self):
        block_structures = TestRainfallDataFromHirds.get_block_structures(
            self.depth_layout, self.intensity_layout, start=2)
        for block_structure in block_structures:
            self.assertFalse(math.isnan(block_structure.rcp))

    def test_get_layout_structure_of_data_time_period_none(self):
        block_structures = TestRainfallDataFromHirds.get_block_structures(
            self.depth_layout, self.intensity_layout, end=2)
        for block_structure in block_structures:
            self.assertIsNone(block_structure.time_period)

    def test_get_layout_structure_of_data_time_period_not_none(self):
        block_structures = TestRainfallDataFromHirds.get_block_structures(
            self.depth_layout, self.intensity_layout, start=2)
        for block_structure in block_structures:
            self.assertIsNotNone(block_structure.time_period)

    def test_get_layout_structure_of_data_category_hist(self):
        block_structures = TestRainfallDataFromHirds.get_block_structures(
            self.depth_layout, self.intensity_layout, end=1)
        for block_structure in block_structures:
            self.assertEqual(block_structure.category, "hist")

    def test_get_layout_structure_of_data_category_hist_stderr(self):
        block_structures = TestRainfallDataFromHirds.get_block_structures(
            self.depth_layout, self.intensity_layout, start=1, end=2)
        for block_structure in block_structures:
            self.assertEqual(block_structure.category, "hist_stderr")

    def test_get_layout_structure_of_data_category_proj(self):
        block_structures = TestRainfallDataFromHirds.get_block_structures(
            self.depth_layout, self.intensity_layout, start=2)
        for block_structure in block_structures:
            self.assertEqual(block_structure.category, "proj")

    # def test_convert_to_tabular_data_expected_rows_columns_size(self):
    #
    #     for block_structure in self.depth_layout:
    #         rain_table = rainfall_data_from_hirds.convert_to_tabular_data(self.rainfall_depth, self.example_site_id, block_structure)
    #         self.assertEqual(rain_table.shape, )
    #
    #     for block_structure in depth_layout:
    #         rain_table = rainfall_data_from_hirds.convert_to_tabular_data(rainfall_depth, example_site_id, block_structure)
    #         print(rain_table)
    #         rain_table.shape # (12 rows, 18 columns)
    #         rain_table.size # 216 elements = 12 * 18
    #
    #     self.rainfall_depth
    #     self.rainfall_intensity
    #     self.depth_historical
    #
    #     self.depth_layout
    #     self.intensity_layout
    #     self.depth_hist_layout
    #
    #
    #      = rainfall_data_from_hirds.convert_to_tabular_data(site_data, self.example_site_id, block_structure)


if __name__ == "__main__":
    unittest.main()

