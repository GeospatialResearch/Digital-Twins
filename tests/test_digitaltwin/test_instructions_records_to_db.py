"""Tests for the 'cache_length' field added to instructions_records_to_db.py."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

from eddie.digitaltwin import instructions_records_to_db as irdb


class ParseCacheLengthTest(unittest.TestCase):
    """Tests for parse_cache_length."""

    def test_single_unit_values(self):
        self.assertEqual(irdb.parse_cache_length("15d"), pd.Timedelta(days=15))
        self.assertEqual(irdb.parse_cache_length("2w"), pd.Timedelta(days=14))
        self.assertEqual(irdb.parse_cache_length("1y"), pd.Timedelta(days=365))

    def test_combined_units(self):
        self.assertEqual(irdb.parse_cache_length("2w3d"), pd.Timedelta(days=17))
        self.assertEqual(irdb.parse_cache_length("1y2w3d"), pd.Timedelta(days=365 + 14 + 3))

    def test_rejects_empty_or_none(self):
        with self.assertRaises(ValueError):
            irdb.parse_cache_length("")
        with self.assertRaises(ValueError):
            irdb.parse_cache_length(None)

    def test_rejects_unknown_unit(self):
        with self.assertRaises(ValueError):
            irdb.parse_cache_length("5m")

    def test_rejects_malformed_string(self):
        with self.assertRaises(ValueError):
            irdb.parse_cache_length("abc")
        with self.assertRaises(ValueError):
            irdb.parse_cache_length("10")


class ValidateInstructionFieldsTest(unittest.TestCase):
    """Tests for validate_instruction_fields, including the new 'cache_length' field."""

    def test_missing_fetch_mode_raises(self):
        with self.assertRaises(ValueError):
            irdb.validate_instruction_fields("section", {})

    def test_invalid_fetch_mode_raises(self):
        with self.assertRaises(ValueError):
            irdb.validate_instruction_fields("section", {"fetch_mode": "bogus"})

    def test_aoi_without_unique_column_name_raises(self):
        with self.assertRaises(ValueError):
            irdb.validate_instruction_fields("section", {"fetch_mode": "aoi"})

    def test_full_with_unique_column_name_raises(self):
        with self.assertRaises(ValueError):
            irdb.validate_instruction_fields(
                "section", {"fetch_mode": "full", "unique_column_name": "id"})

    def test_valid_full_without_cache_length(self):
        irdb.validate_instruction_fields("section", {"fetch_mode": "full"})

    def test_valid_aoi_with_unique_column_name(self):
        irdb.validate_instruction_fields("section", {"fetch_mode": "aoi", "unique_column_name": "id"})

    def test_valid_cache_length_on_full(self):
        irdb.validate_instruction_fields("section", {"fetch_mode": "full", "cache_length": "1y"})

    def test_valid_cache_length_on_aoi(self):
        irdb.validate_instruction_fields(
            "section", {"fetch_mode": "aoi", "unique_column_name": "id", "cache_length": "2w3d"})

    def test_invalid_cache_length_raises(self):
        with self.assertRaises(ValueError):
            irdb.validate_instruction_fields("section", {"fetch_mode": "full", "cache_length": "not-a-duration"})


class GetUpdatedCacheLengthRecordsTest(unittest.TestCase):
    """Tests for get_updated_cache_length_records."""

    def test_detects_changed_value(self):
        instructions_df = pd.DataFrame([{"data_provider": "LINZ", "layer_id": 1, "cache_length": "2w"}])
        existing_df = pd.DataFrame([{"data_provider": "LINZ", "layer_id": 1, "cache_length": "1w"}])
        result = irdb.get_updated_cache_length_records(instructions_df, existing_df)
        self.assertEqual(result["cache_length"].tolist(), ["2w"])

    def test_detects_cleared_value(self):
        instructions_df = pd.DataFrame([{"data_provider": "LINZ", "layer_id": 1, "cache_length": None}])
        existing_df = pd.DataFrame([{"data_provider": "LINZ", "layer_id": 1, "cache_length": "1w"}])
        result = irdb.get_updated_cache_length_records(instructions_df, existing_df)
        self.assertEqual(len(result), 1)

    def test_detects_newly_set_value(self):
        instructions_df = pd.DataFrame([{"data_provider": "LINZ", "layer_id": 1, "cache_length": "1w"}])
        existing_df = pd.DataFrame([{"data_provider": "LINZ", "layer_id": 1, "cache_length": None}])
        result = irdb.get_updated_cache_length_records(instructions_df, existing_df)
        self.assertEqual(len(result), 1)

    def test_unchanged_value_not_flagged(self):
        instructions_df = pd.DataFrame([{"data_provider": "LINZ", "layer_id": 1, "cache_length": "1w"}])
        existing_df = pd.DataFrame([{"data_provider": "LINZ", "layer_id": 1, "cache_length": "1w"}])
        result = irdb.get_updated_cache_length_records(instructions_df, existing_df)
        self.assertTrue(result.empty)

    def test_both_unset_not_flagged(self):
        instructions_df = pd.DataFrame([{"data_provider": "LINZ", "layer_id": 1, "cache_length": None}])
        existing_df = pd.DataFrame([{"data_provider": "LINZ", "layer_id": 1, "cache_length": None}])
        result = irdb.get_updated_cache_length_records(instructions_df, existing_df)
        self.assertTrue(result.empty)

    def test_new_record_not_in_existing_is_ignored(self):
        instructions_df = pd.DataFrame([{"data_provider": "LINZ", "layer_id": 2, "cache_length": "1w"}])
        existing_df = pd.DataFrame([{"data_provider": "LINZ", "layer_id": 1, "cache_length": None}])
        result = irdb.get_updated_cache_length_records(instructions_df, existing_df)
        self.assertTrue(result.empty)


class ReadAndCheckInstructionsFileTest(unittest.TestCase):
    """Tests that 'cache_length' is parsed/defaulted correctly when reading the instructions file."""

    @staticmethod
    def _write_instructions(tmp_dir, instructions):
        path = Path(tmp_dir) / "instructions.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(instructions, f)
        return path

    def test_none_path_returns_empty_df_with_cache_length_column(self):
        df = irdb.read_and_check_instructions_file(None)
        self.assertIn("cache_length", df.columns)
        self.assertTrue(df.empty)

    @mock.patch.object(irdb, "validate_url_reachability")
    def test_cache_length_defaults_to_none_when_absent(self, _):
        instructions = {
            "layer_one": {
                "data_provider": "LINZ", "layer_id": 1, "table_name": "t1",
                "fetch_mode": "full", "url": "http://example.com",
            }
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._write_instructions(tmp_dir, instructions)
            df = irdb.read_and_check_instructions_file(path)
        self.assertIsNone(df.loc[0, "cache_length"])

    @mock.patch.object(irdb, "validate_url_reachability")
    def test_cache_length_preserved_when_present(self, _):
        instructions = {
            "layer_one": {
                "data_provider": "LINZ", "layer_id": 1, "table_name": "t1",
                "fetch_mode": "full", "url": "http://example.com", "cache_length": "1y",
            }
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._write_instructions(tmp_dir, instructions)
            df = irdb.read_and_check_instructions_file(path)
        self.assertEqual(df.loc[0, "cache_length"], "1y")

    @mock.patch.object(irdb, "validate_url_reachability")
    def test_mixed_presence_normalises_missing_to_none(self, _):
        instructions = {
            "layer_one": {
                "data_provider": "LINZ", "layer_id": 1, "table_name": "t1",
                "fetch_mode": "full", "url": "http://example.com", "cache_length": "1y",
            },
            "layer_two": {
                "data_provider": "LINZ", "layer_id": 2, "table_name": "t2",
                "fetch_mode": "full", "url": "http://example.com",
            },
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._write_instructions(tmp_dir, instructions)
            df = irdb.read_and_check_instructions_file(path)
        cache_lengths = dict(zip(df["section"], df["cache_length"]))
        self.assertEqual(cache_lengths["layer_one"], "1y")
        self.assertIsNone(cache_lengths["layer_two"])

    @mock.patch.object(irdb, "validate_url_reachability")
    def test_invalid_cache_length_in_file_raises(self, _):
        instructions = {
            "layer_one": {
                "data_provider": "LINZ", "layer_id": 1, "table_name": "t1",
                "fetch_mode": "full", "url": "http://example.com", "cache_length": "nope",
            }
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._write_instructions(tmp_dir, instructions)
            with self.assertRaises(ValueError):
                irdb.read_and_check_instructions_file(path)


if __name__ == "__main__":
    unittest.main()
