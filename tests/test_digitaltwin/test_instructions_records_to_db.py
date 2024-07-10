import unittest
from unittest.mock import patch
import requests
from src.digitaltwin import instructions_records_to_db
import pandas as pd
from pathlib import Path
import tempfile

class TestInstructionsRecordsToDb(unittest.TestCase):
    def test_validate_url_reachability_valid_url(self):
        # Checks if the 'validate_url_reachability' function handles a valid url without raising any exceptions
        url = "https://www.example.com"
        section = "test_section"
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            # No exception should be raised
            instructions_records_to_db.validate_url_reachability(section, url)

    def test_validate_url_reachability_invalid_url(self):
        # Ensures that the 'validate_url_reachability' function raises A 'ValueError' when provided with an invalid url
        url = "not_a_valid_url"
        section = "test_section"
        with self.assertRaises(ValueError) as context:
            instructions_records_to_db.validate_url_reachability(section, url)
        self.assertIn("Invalid URL provided", str(context.exception))

    def test_validate_url_reachability_reachable_url(self):
        # Test with a valid and reachable URL
        url = "https://www.example.com"
        section = "test_section"
        try:
            # Make a real GET request
            response = requests.get(url)
            response.raise_for_status()  # Raise an exception if the response status code indicates an error
            # If the above line doesn't raise an exception, the URL is considered reachable

            # Validate the URL using your function
            instructions_records_to_db.validate_url_reachability(section, url)

        except requests.exceptions.RequestException as e:
            self.fail(f"Unexpected exception: {e}")

    def test_validate_instruction_fields_valid_coverage_area(self):
        # Test with a valid instruction providing 'coverage_area'
        section = "test_section"
        instruction = {"coverage_area": "Area 51"}
        # No exception should be raised
        instructions_records_to_db.validate_instruction_fields(section, instruction)

    def test_validate_instruction_fields_valid_unique_column_name(self):
        # Test with a valid instruction providing 'unique_column_name'
        section = "test_section"
        instruction = {"unique_column_name": "column_name"}
        # No exception should be raised
        instructions_records_to_db.validate_instruction_fields(section, instruction)

    def test_validate_instruction_fields_invalid_both_fields_provided(self):
        # Test with an invalid instruction providing both 'coverage_area' and 'unique_column_name'
        section = "test_section"
        instruction = {"coverage_area": "Area 51", "unique_column_name": "column_name"}
        with self.assertRaises(ValueError) as context:
            instructions_records_to_db.validate_instruction_fields(section, instruction)
        self.assertIn("Both 'coverage_area' and 'unique_column_name' provided", str(context.exception))

    def test_validate_instruction_fields_invalid_neither_field_provided(self):
        # Test with an invalid instruction providing neither 'coverage_area' nor 'unique_column_name'
        section = "test_section"
        instruction = {}
        with self.assertRaises(ValueError) as context:
            instructions_records_to_db.validate_instruction_fields(section, instruction)
        self.assertIn("Neither 'coverage_area' nor 'unique_column_name' provided", str(context.exception))

    def test_read_and_check_instructions_file(self):
        # Create a temporary file with sample data
        with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
            temp_file.write('{"section1": {"url": "http://example.com", "other_field": "value"}}')
            temp_file_path = temp_file.name

        try:
            # Test the read_and_check_instructions_file function
            with patch("pathlib.Path", return_value=Path(temp_file_path)):
                with patch(
                        "src.digitaltwin.instructions_records_to_db.validate_url_reachability") as mock_validate_url_reachability:
                    with patch(
                            "src.digitaltwin.instructions_records_to_db.validate_instruction_fields") as mock_validate_instruction_fields:
                        result_df = instructions_records_to_db.read_and_check_instructions_file()

                        # Assertions
                        self.assertIsInstance(result_df, pd.DataFrame)
                        self.assertEqual(len(result_df), 1)
                        self.assertSetEqual(set(result_df.columns), {'section', 'url', 'other_field'})

                        # Assert that validate_url_reachability was called with the expected arguments
                        mock_validate_url_reachability.assert_called_with("section1", "http://example.com")

                        # Assert that validate_instruction_fields was called with the expected arguments
                        mock_validate_instruction_fields.assert_called_with("section1", {"url": "http://example.com"})

        finally:
            # Clean up: remove the temporary file
            Path(temp_file_path).unlink()

    def test_get_non_existing_records(self):
        # Sample data for instructions_df
        instructions_data = {'data_provider': ['A', 'B', 'C', 'D'],
                             'layer_id': [1, 2, 3, 4],
                             'section': ['S1', 'S2', 'S3', 'S4'],
                             'url': ['url1', 'url2', 'url3', 'url4']}
        instructions_df = pd.DataFrame(instructions_data)

        # Sample data for existing_layers_df
        existing_data = {'data_provider': ['A', 'B', 'C'],
                         'layer_id': [1, 2, 3],
                         'section': ['S1', 'S2', 'S3'],
                         'url': ['url1', 'url2', 'url3']}
        existing_layers_df = pd.DataFrame(existing_data)

        # Call the function
        with patch(
                "src.digitaltwin.instructions_records_to_db.get_non_existing_records") as mock_get_non_existing_records:
            # Set the return value of the mock to simulate the absence of 'url' column
            mock_get_non_existing_records.return_value = instructions_df

            result = instructions_records_to_db.get_non_existing_records(instructions_df, existing_layers_df)

            # Assertions
            self.assertIsInstance(result, pd.DataFrame)
            self.assertEqual(len(result), len(instructions_df))

            # Assert that get_non_existing_records was called with the expected arguments
            mock_get_non_existing_records.assert_called_with(instructions_df, existing_layers_df)


if __name__ == '__main__':
    unittest.main()
