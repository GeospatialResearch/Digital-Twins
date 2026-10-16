"""Tests for the standalone expired_cache.py cache cleanup script."""
import unittest
from unittest import mock

from eddie.digitaltwin import expired_cache


class DeleteExpiredFullLayerTablesTest(unittest.TestCase):
    """Tests for delete_expired_full_layer_tables."""

    def test_drops_only_tables_that_still_exist_and_updates_columns(self):
        conn = mock.MagicMock()
        # conn.execute() is called for: the SELECT of expired table names, one DROP TABLE, then the final UPDATE
        conn.execute.side_effect = [
            [("table_a",), ("table_b",)],
            mock.MagicMock(),
            mock.MagicMock(),
        ]
        with mock.patch.object(
            expired_cache, "check_table_exists", side_effect=lambda _, name: name == "table_a"
        ), mock.patch.object(expired_cache, "update") as update_mock:
            expired_cache.delete_expired_full_layer_tables(conn)

        self.assertEqual(conn.execute.call_count, 3)
        drop_sql = str(conn.execute.call_args_list[1].args[0])
        self.assertIn("table_a", drop_sql)
        self.assertNotIn("table_b", drop_sql)
        update_mock.return_value.where.return_value.values.assert_called_once_with(
            fetched_at=None, refresh_after=None)

    def test_no_update_when_nothing_expired(self):
        conn = mock.MagicMock()
        conn.execute.side_effect = [[]]
        with mock.patch.object(expired_cache, "check_table_exists") as check_exists, \
             mock.patch.object(expired_cache, "update") as update_mock:
            expired_cache.delete_expired_full_layer_tables(conn)
        check_exists.assert_not_called()
        update_mock.assert_not_called()
        conn.execute.assert_called_once()


class DeleteExpiredUserLogEntriesTest(unittest.TestCase):
    """Tests for delete_expired_user_log_entries."""

    def test_returns_zero_when_table_missing(self):
        conn = mock.MagicMock()
        with mock.patch.object(expired_cache, "check_table_exists", return_value=False):
            result = expired_cache.delete_expired_user_log_entries(conn)
        self.assertEqual(result, 0)
        conn.execute.assert_not_called()

    def test_deletes_and_returns_rowcount(self):
        conn = mock.MagicMock()
        conn.execute.return_value.rowcount = 5
        with mock.patch.object(expired_cache, "check_table_exists", return_value=True), \
             mock.patch.object(expired_cache, "delete") as delete_mock:
            result = expired_cache.delete_expired_user_log_entries(conn)
        self.assertEqual(result, 5)
        delete_mock.assert_called_once_with(expired_cache.UserLogInfo)
        conn.execute.assert_called_once_with(delete_mock.return_value.where.return_value)


class DeleteExpiredCacheTest(unittest.TestCase):
    """Tests that delete_expired_cache orchestrates both cleanup steps."""

    def test_calls_both_cleanup_functions(self):
        conn = mock.MagicMock()
        with mock.patch.object(expired_cache, "delete_expired_full_layer_tables") as full_mock, \
             mock.patch.object(expired_cache, "delete_expired_user_log_entries") as log_mock:
            expired_cache.delete_expired_cache(conn)
        full_mock.assert_called_once_with(conn)
        log_mock.assert_called_once_with(conn)


if __name__ == "__main__":
    unittest.main()
