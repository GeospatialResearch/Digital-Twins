"""Tests for data_to_db.py"""
import unittest
from datetime import datetime, timezone
from unittest import mock

import geopandas as gpd
import pandas as pd
import shapely

from eddie.digitaltwin import data_to_db, get_data_using_geoapis, nz_providers


class IsRefreshExpiredTest(unittest.TestCase):
    """Tests for is_refresh_expired."""

    def test_none_never_expires(self):
        self.assertFalse(data_to_db.is_refresh_expired(None))

    def test_nat_never_expires(self):
        self.assertFalse(data_to_db.is_refresh_expired(pd.NaT))

    def test_future_date_not_expired(self):
        future = pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=1)
        self.assertFalse(data_to_db.is_refresh_expired(future))

    def test_past_date_is_expired(self):
        past = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=1)
        self.assertTrue(data_to_db.is_refresh_expired(past))


class UpdateFetchedAtTest(unittest.TestCase):
    """Tests for update_fetched_at and update_full_layer_cache_expiry."""

    @mock.patch.object(data_to_db, "update")
    def test_update_fetched_at_sets_fetched_at(self, update_mock):
        conn = mock.MagicMock()
        fixed_now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with mock.patch.object(data_to_db, "datetime") as datetime_mock:
            datetime_mock.now.return_value = fixed_now
            data_to_db.update_fetched_at(conn, "LINZ", 1)
        values_call = update_mock.return_value.where.return_value.values
        values_call.assert_called_once_with(fetched_at=fixed_now)
        conn.execute.assert_called_once()

    @mock.patch.object(data_to_db, "update")
    def test_cache_expiry_computes_refresh_after_from_cache_length(self, update_mock):
        conn = mock.MagicMock()
        fixed_now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with mock.patch.object(data_to_db, "datetime") as datetime_mock:
            datetime_mock.now.return_value = fixed_now
            data_to_db.update_full_layer_cache_expiry(conn, "LINZ", 1, "2w3d")
        values_call = update_mock.return_value.where.return_value.values
        values_call.assert_called_once_with(fetched_at=fixed_now, refresh_after=fixed_now + pd.Timedelta(days=17))

    @mock.patch.object(data_to_db, "update")
    def test_cache_expiry_none_when_no_cache_length(self, update_mock):
        conn = mock.MagicMock()
        fixed_now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with mock.patch.object(data_to_db, "datetime") as datetime_mock:
            datetime_mock.now.return_value = fixed_now
            data_to_db.update_full_layer_cache_expiry(conn, "LINZ", 1, None)
        values_call = update_mock.return_value.where.return_value.values
        values_call.assert_called_once_with(fetched_at=fixed_now, refresh_after=None)


class FullGeospatialLayersRefetchTest(unittest.TestCase):
    """Tests that 'full' fetch_mode layers are only re-fetched when missing or their 'refresh_after' has expired."""

    def _run(self, table_exists, refresh_after):
        layers_df = pd.DataFrame([{
            "data_provider": "LINZ", "layer_id": 1, "table_name": "layer_a",
            "unique_column_name": None, "cache_length": "1d", "refresh_after": refresh_after,
            "fetched_at": pd.NaT,
        }])
        conn = mock.MagicMock()
        fetched = gpd.GeoDataFrame({"id": [1]}, geometry=[shapely.Point(0, 0)], crs=4326)
        with mock.patch.object(data_to_db, "get_full_geospatial_layers", return_value=layers_df), \
            mock.patch.object(data_to_db, "check_table_exists", return_value=table_exists), \
            mock.patch.object(get_data_using_geoapis, "fetch_vector_data_using_geoapis",
                              return_value=fetched) as fetch_mock, \
            mock.patch.object(data_to_db, "update_full_layer_cache_expiry") as update_mock, \
            mock.patch.object(data_to_db, "gs"), \
            mock.patch.object(gpd.GeoDataFrame, "to_postgis", autospec=True) as to_postgis:
            data_to_db.full_geospatial_layers_data_to_db(conn, 2193)
        return conn, fetch_mock, to_postgis, update_mock

    def test_skips_existing_unexpired_table(self):
        future = pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=1)
        _, fetch_mock, to_postgis, update_mock = self._run(table_exists=True, refresh_after=future)
        fetch_mock.assert_not_called()
        to_postgis.assert_not_called()
        update_mock.assert_not_called()


class NonIntersectionAreaExpiryFilterTest(unittest.TestCase):
    """Tests that the user log intersection query excludes expired log entries."""

    @mock.patch.object(data_to_db, "create_user_log_table")
    def test_query_filters_out_expired_entries(self, _):
        ao = gpd.GeoDataFrame(geometry=[shapely.box(0, 0, 1, 1)], crs=4326)
        conn = mock.MagicMock()
        empty = gpd.GeoDataFrame(geometry=[], crs=4326)
        with mock.patch.object(gpd.GeoDataFrame, "from_postgis", return_value=empty) as from_postgis:
            data_to_db.get_non_intersection_area_from_db(conn, ao, "layer")
        query = from_postgis.call_args.args[0]
        self.assertIn("refresh_after", str(query))


class UserLogInfoRefreshAfterTest(unittest.TestCase):
    """Tests that user_log_info_to_db computes 'refresh_after' from the soonest aoi layer 'cache_length'."""

    def _run(self, cache_lengths):
        aoi_layers = pd.DataFrame({
            "table_name": [f"t{i}" for i in range(len(cache_lengths))],
            "cache_length": cache_lengths,
        })
        catchment = gpd.GeoDataFrame(geometry=[shapely.box(0, 0, 1, 1)], crs=4326)
        conn = mock.MagicMock()
        fixed_now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with mock.patch.object(data_to_db, "create_user_log_table"), \
            mock.patch.object(data_to_db, "get_aoi_geospatial_layers", return_value=aoi_layers), \
            mock.patch.object(data_to_db, "insert") as insert_mock, \
            mock.patch.object(data_to_db, "datetime") as datetime_mock:
            datetime_mock.now.return_value = fixed_now
            data_to_db.user_log_info_to_db(conn, catchment)
        return insert_mock.return_value.values.call_args.kwargs, fixed_now

    def test_uses_soonest_cache_length(self):
        values, fixed_now = self._run(["1w", "2d", None])
        self.assertEqual(values["refresh_after"], fixed_now + pd.Timedelta(days=2))

    def test_none_when_no_cache_length_configured(self):
        values, _ = self._run([None, None])
        self.assertIsNone(values["refresh_after"])


class AppendToExistingLayerTest(unittest.TestCase):
    """Tests that data fetched in one working CRS is appended in the CRS the layer table was created in."""

    @mock.patch.object(data_to_db.gs, "create_main_db_store", return_value="store")
    @mock.patch.object(data_to_db.gs, "create_datastore_layer")
    @mock.patch.object(data_to_db, "get_vector_data_id_not_in_db", return_value={1})
    @mock.patch.object(nz_providers, "fetch_vector_data_using_geoapis")
    def test_reprojects_to_table_crs(self, fetch, _, create_layer, _store):
        # Fetched in UTM zone 60 (an Auckland request) for a table created in UTM zone 59 (a Christchurch request)
        fetched = gpd.GeoDataFrame({"id": [1]}, crs=4326, geometry=[shapely.Point(174.76, -36.85)]).to_crs(32760)
        fetch.return_value = fetched
        conn = mock.MagicMock()
        conn.execute.return_value.scalar.return_value = 32759
        aoi = gpd.GeoDataFrame(index=[0], crs=32760, geometry=[fetched.buffer(100).geometry[0]])
        with mock.patch.object(gpd.GeoDataFrame, "to_postgis", autospec=True) as to_postgis:
            data_to_db.process_existing_aoi_geospatial_layers(conn, "LINZ", 1, "layer", "id", aoi, 32760)
        appended = to_postgis.call_args.args[0]
        self.assertEqual(appended.crs.to_epsg(), 32759)
        self.assertTrue(appended.geometry[0].equals_exact(fetched.to_crs(32759).geometry[0], 1e-6))
        # The served layer is refreshed so its bounds include the appended data
        self.assertIn('ANALYZE "layer"', [str(call.args[0]) for call in conn.execute.call_args_list])
        create_layer.assert_called_once_with(data_to_db.gs.Workspaces.INPUT_LAYERS_WORKSPACE, "store", "layer")


class AoiSridTest(unittest.TestCase):
    """Tests that the AOI is bound in the CRS it came with, else EPSG:4326."""

    def bound_srid(self, aoi: gpd.GeoDataFrame) -> int:
        with mock.patch.object(data_to_db.pd, "read_sql", return_value=pd.DataFrame({"id": []})) as read_sql:
            data_to_db.get_vector_data_id_not_in_db(mock.MagicMock(), pd.DataFrame({"id": [1]}), "layer", "id", aoi)
        return read_sql.call_args.args[0].compile().params["aoi_srid"]

    def test_crs_from_the_aoi(self):
        self.assertEqual(self.bound_srid(gpd.GeoDataFrame(geometry=[shapely.box(0, 0, 1, 1)], crs=32759)), 32759)

    def test_4326_without_crs(self):
        self.assertEqual(self.bound_srid(gpd.GeoDataFrame(geometry=[shapely.box(0, 0, 1, 1)])), 4326)


class NonIntersectionAreaTest(unittest.TestCase):
    """Tests that an area logged before counts as fully covered, whatever the working CRS."""

    @mock.patch.object(data_to_db, "create_user_log_table")
    def test_same_area_is_covered(self, _):
        aoi = gpd.GeoDataFrame(geometry=[shapely.box(174.76, -36.86, 174.78, -36.84)], crs=4326).to_crs(32760)
        # What user_log_info_to_db stored for the same request, read back from the database
        logged = gpd.GeoDataFrame(geometry=[shapely.from_wkt(aoi.to_crs(4326).geometry[0].wkt)], crs=4326)
        conn = mock.MagicMock()
        with mock.patch.object(gpd.GeoDataFrame, "from_postgis", return_value=logged):
            with self.assertRaises(data_to_db.NoNonIntersectionError):
                data_to_db.get_non_intersection_area_from_db(conn, aoi, "layer")


if __name__ == "__main__":
    unittest.main()
