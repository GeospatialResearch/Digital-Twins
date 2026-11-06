"""Tests for the 'cache_length' field added to instructions_records_to_db.py."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd
import pytest

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

    @pytest.mark.xfail(raises=AssertionError, strict=True,
                       reason="BUG: 'AOI' passes validation via .lower() but is stored as given, so the "
                              "fetch_mode = 'aoi' queries and CHECK constraint never match it. Remove when fixed.")
    @mock.patch.object(irdb, "validate_url_reachability")
    def test_fetch_mode_normalised_to_lowercase(self, _):
        instructions = {
            "layer_one": {
                "data_provider": "LINZ", "layer_id": "1", "table_name": "t1", "fetch_mode": "AOI",
                "unique_column_name": "id", "url": "http://example.com",
            }
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._write_instructions(tmp_dir, instructions)
            df = irdb.read_and_check_instructions_file(path)
        self.assertEqual(df.loc[0, "fetch_mode"], "aoi")


def _instructions(*layer_ids, cache_length=None):
    """Instructions rows as read_and_check_instructions_file returns them (object columns), one LINZ layer per id."""
    return pd.DataFrame([{
        "section": f"layer_{layer_id}", "data_provider": "LINZ", "layer_id": layer_id, "url": "http://example.com",
        "table_name": f"t{layer_id}", "fetch_mode": "full", "unique_column_name": None, "cache_length": cache_length,
    } for layer_id in layer_ids], dtype=object)


def _existing(*layer_ids, cache_length=None):
    """Rows as get_existing_geospatial_layers returns them; 'layer_id' is a String column in the database."""
    return pd.DataFrame({
        "data_provider": ["LINZ"] * len(layer_ids),
        "layer_id": list(layer_ids),
        "cache_length": [cache_length] * len(layer_ids),
    }, dtype=object)


class GetNonExistingRecordsTest(unittest.TestCase):
    """Tests for get_non_existing_records."""

    def test_returns_only_records_not_in_db(self):
        result = irdb.get_non_existing_records(_instructions("1", "2"), _existing("1", "3"))
        self.assertEqual(result["layer_id"].tolist(), ["2"])

    def test_same_layer_id_from_another_provider_is_new(self):
        existing = _existing("1").assign(data_provider="MFE")
        result = irdb.get_non_existing_records(_instructions("1"), existing)
        self.assertEqual(result["layer_id"].tolist(), ["1"])

    def test_drops_section_and_moves_url_last(self):
        result = irdb.get_non_existing_records(_instructions("2"), _existing())
        self.assertNotIn("section", result.columns)
        self.assertNotIn("_merge", result.columns)
        self.assertEqual(result.columns[-1], "url")
        self.assertEqual(result["table_name"].tolist(), ["t2"])

    def test_all_existing_returns_empty(self):
        result = irdb.get_non_existing_records(_instructions("1"), _existing("1"))
        self.assertTrue(result.empty)

    @pytest.mark.xfail(raises=AssertionError, strict=True,
                       reason="BUG: a JSON integer layer_id never equals the String layer_id read back from the "
                              "database, so the layer is appended again on every startup. Remove when fixed.")
    @mock.patch.object(irdb, "validate_url_reachability")
    def test_numeric_layer_id_matches_stored_string(self, _):
        # Read the layer from a file, so this flips to XPASS whether the fix casts layer_id in the reader or the merge
        instructions = {
            "layer_1": {"data_provider": "LINZ", "layer_id": 1, "table_name": "t1", "fetch_mode": "full",
                        "url": "http://example.com"}
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = ReadAndCheckInstructionsFileTest._write_instructions(tmp_dir, instructions)
            instructions_df = irdb.read_and_check_instructions_file(path)
        result = irdb.get_non_existing_records(instructions_df, _existing("1"))
        self.assertTrue(result.empty)


class StoreInstructionsRecordsToDbTest(unittest.TestCase):
    """Tests for store_instructions_records_to_db."""

    def _run(self, instructions_df, existing_df):
        conn = mock.MagicMock()
        with mock.patch.object(irdb, "create_table") as create_mock, \
            mock.patch.object(irdb, "get_existing_geospatial_layers", return_value=existing_df), \
            mock.patch.object(irdb, "read_and_check_instructions_file", return_value=instructions_df) as read_mock, \
            mock.patch.object(pd.DataFrame, "to_sql", autospec=True) as to_sql, \
            mock.patch.object(irdb, "update") as update_mock:
            irdb.store_instructions_records_to_db(conn, Path("instructions.json"))
        create_mock.assert_called_once_with(conn, irdb.GeospatialLayers)
        read_mock.assert_called_once_with(Path("instructions.json"))
        return conn, to_sql, update_mock

    def test_appends_only_new_records(self):
        conn, to_sql, update_mock = self._run(_instructions("1", "2"), _existing("1"))
        to_sql.assert_called_once()
        appended = to_sql.call_args.args[0]
        self.assertEqual(appended["layer_id"].tolist(), ["2"])
        self.assertEqual(to_sql.call_args.args[1:], ("geospatial_layers", conn))
        self.assertEqual(to_sql.call_args.kwargs, {"index": False, "if_exists": "append"})
        update_mock.assert_not_called()

    def test_nothing_new_writes_nothing(self):
        conn, to_sql, update_mock = self._run(_instructions("1"), _existing("1"))
        to_sql.assert_not_called()
        update_mock.assert_not_called()
        conn.execute.assert_not_called()

    def test_changed_cache_length_is_updated(self):
        conn, to_sql, update_mock = self._run(_instructions("1", cache_length="2d"), _existing("1", cache_length="1w"))
        to_sql.assert_not_called()
        update_mock.assert_called_once_with(irdb.GeospatialLayers)
        values_call = update_mock.return_value.where.return_value.values
        values_call.assert_called_once_with(cache_length="2d")
        conn.execute.assert_called_once_with(values_call.return_value)


if __name__ == "__main__":
    unittest.main()
