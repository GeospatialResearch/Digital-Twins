import unittest
from unittest.mock import MagicMock, patch
import pandas as pd

from src.digitaltwin.setup_environment import get_database
from src.digitaltwin.data_to_db import get_nz_geospatial_layers

class TestDataToDB(unittest.TestCase):
    @classmethod
    @patch("src.digitaltwin.setup_environment.get_connection_from_profile", autospec=True)
    def setUpClass(cls, mock_get_connection):
        # Set up a mock database engine
        mock_engine = MagicMock()

        # Mock the SQL query result
        mock_query_result = pd.DataFrame({
            'column1': [1, 2, 3],
            'column2': ['A', 'B', 'C']
            # Add more columns as needed
        })

        # Configure the mock engine to return the query result
        mock_engine.execute.return_value.fetchall.return_value = mock_query_result.values

        # Mock the database connection setup function
        mock_get_connection.return_value = mock_engine

        # Call the function with the mock engine
        cls.dataframe_output = get_nz_geospatial_layers(mock_engine)

    def test_get_nz_geospatial_layers_correct_frame_type(self):
        """Test to ensure tabular data is returned in DataFrame format."""
        self.assertIsInstance(self.dataframe_output, pd.DataFrame)

if __name__ == '__main__':
    unittest.main()
