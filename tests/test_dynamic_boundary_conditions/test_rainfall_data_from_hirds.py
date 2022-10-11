import math
import unittest
from typing import List

from src.dynamic_boundary_conditions import rainfall_data_from_hirds


class TestRainfallDataFromHirds(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        filename = "tests/test_dynamic_boundary_conditions/data/hirds_output.txt"
        with open(filename) as in_file:
            cls.hirds_output = in_file.read()

    def test_get_data_from_hirds_not_empty(self):
        example_site = '323605'
        data = rainfall_data_from_hirds.get_data_from_hirds(example_site, False)
        self.assertGreater(len(data), 0)

    def test_get_data_from_hirds_correct_format(self):
        pass

    def test_get_layout_structure_of_data_just_one_block(self):
        layout_structure = layout_structure_from_filename(
            "tests/test_dynamic_boundary_conditions/data/historical_depth.txt")
        self.assertEqual(len(layout_structure), 1)

    def test_get_layout_structure_of_data_rcp_nan(self):
        layout_structure = layout_structure_from_filename(
            "tests/test_dynamic_boundary_conditions/data/historical_depth.txt")
        rcp = layout_structure[0].rcp
        self.assertTrue(math.isnan(rcp))


def layout_structure_from_filename(filename: str) -> List[rainfall_data_from_hirds.BlockStructure]:
    site_data = file_to_string(filename)
    return rainfall_data_from_hirds.get_layout_structure_of_data(site_data)


def file_to_string(filename: str) -> str:
    with open(filename) as in_file:
        return in_file.read()


if __name__ == '__main__':
    unittest.main()
