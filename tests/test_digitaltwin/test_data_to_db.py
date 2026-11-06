"""Tests for data_to_db.py"""
import unittest
from datetime import datetime, timezone
from unittest import mock

import geopandas as gpd
import pandas as pd
import shapely

from eddie.digitaltwin import data_to_db, nz_providers, provider_registry


class LayerQueryFetchModeTest(unittest.TestCase):
    """Tests for get_full_geospatial_layers and get_aoi_geospatial_layers."""

    def _run(self, get_layers):
        layers = pd.DataFrame({"unique_id": [7], "table_name": ["layer_a"]})
        conn = mock.MagicMock()
        with mock.patch.object(data_to_db.pd, "read_sql", return_value=layers) as read_sql:
            result = get_layers(conn)
        query, read_conn = read_sql.call_args.args
        self.assertIs(read_conn, conn)
        return result, " ".join(query.split())

    def test_full_query_selects_full_layers_without_unique_column(self):
        result, query = self._run(data_to_db.get_full_geospatial_layers)
        self.assertIn("FROM geospatial_layers", query)
        self.assertIn("fetch_mode = 'full'", query)
        self.assertIn("unique_column_name IS NULL", query)
        self.assertNotIn("aoi", query)
        self.assertNotIn("IS NOT NULL", query)
        self.assertEqual(result.columns.tolist(), ["table_name"])

    def test_aoi_query_selects_aoi_layers_with_unique_column(self):
        result, query = self._run(data_to_db.get_aoi_geospatial_layers)
        self.assertIn("FROM geospatial_layers", query)
        self.assertIn("fetch_mode = 'aoi'", query)
        self.assertIn("unique_column_name IS NOT NULL", query)
        self.assertNotIn("full", query)
        self.assertEqual(result.columns.tolist(), ["table_name"])


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
        # Patch the registry entry the code looks up, not 'fetch_vector_data_using_geoapis': nz_providers holds its
        # own reference to that, so patching it on get_data_using_geoapis never reached the LINZ provider.
        fetch_mock = mock.MagicMock(return_value=fetched)
        with mock.patch.object(data_to_db, "get_full_geospatial_layers", return_value=layers_df), \
            mock.patch.object(data_to_db, "check_table_exists", return_value=table_exists), \
            mock.patch.dict(provider_registry._PROVIDERS, {"LINZ": fetch_mock}), \
            mock.patch.object(data_to_db, "update_full_layer_cache_expiry") as update_mock, \
            mock.patch.object(data_to_db, "gs") as gs_mock, \
            mock.patch.object(gpd.GeoDataFrame, "to_postgis", autospec=True) as to_postgis:
            data_to_db.full_geospatial_layers_data_to_db(conn, 2193)
        return conn, fetch_mock, to_postgis, update_mock, gs_mock, fetched

    def test_skips_existing_unexpired_table(self):
        future = pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=1)
        _, fetch_mock, to_postgis, update_mock, gs_mock, _ = self._run(table_exists=True, refresh_after=future)
        fetch_mock.assert_not_called()
        to_postgis.assert_not_called()
        update_mock.assert_not_called()
        gs_mock.create_datastore_layer.assert_not_called()

    def test_fetches_missing_table(self):
        conn, fetch_mock, to_postgis, update_mock, gs_mock, fetched = self._run(
            table_exists=False, refresh_after=pd.NaT)
        fetch_mock.assert_called_once_with(1, None, 2193)
        to_postgis.assert_called_once_with(fetched, "layer_a", conn, index=False, if_exists="replace")
        gs_mock.create_datastore_layer.assert_called_once_with(
            gs_mock.Workspaces.INPUT_LAYERS_WORKSPACE, gs_mock.create_main_db_store.return_value, "layer_a")
        update_mock.assert_called_once_with(conn, "LINZ", 1, "1d")

    def test_refetches_expired_table(self):
        past = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=1)
        conn, fetch_mock, to_postgis, update_mock, _, fetched = self._run(table_exists=True, refresh_after=past)
        fetch_mock.assert_called_once_with(1, None, 2193)
        to_postgis.assert_called_once_with(fetched, "layer_a", conn, index=False, if_exists="replace")
        update_mock.assert_called_once_with(conn, "LINZ", 1, "1d")


class AoiLayersDispatchTest(unittest.TestCase):
    """Tests that aoi_geospatial_layers_data_to_db fetches only the uncovered area, into a new or existing table."""

    def _run(self, table_exists, covered=False, data_provider="LINZ"):
        layers_df = pd.DataFrame([{
            "data_provider": data_provider, "layer_id": 3, "table_name": "layer_b", "unique_column_name": "id",
        }])
        aoi = gpd.GeoDataFrame(geometry=[shapely.box(0, 0, 1, 1)], crs=2193)
        remainder = gpd.GeoDataFrame(geometry=[shapely.box(0, 0, 1, 0.5)], crs=2193)
        conn = mock.MagicMock()
        side_effect = data_to_db.NoNonIntersectionError("covered") if covered else None
        with mock.patch.dict(provider_registry._PROVIDERS, {"LINZ": mock.MagicMock()}, clear=True), \
            mock.patch.object(data_to_db, "get_aoi_geospatial_layers", return_value=layers_df), \
            mock.patch.object(data_to_db, "get_non_intersection_area_from_db", return_value=remainder,
                              side_effect=side_effect) as non_intersection, \
            mock.patch.object(data_to_db, "check_table_exists", return_value=table_exists) as check_exists, \
            mock.patch.object(data_to_db, "process_existing_aoi_geospatial_layers") as existing_mock, \
            mock.patch.object(data_to_db, "process_new_aoi_geospatial_layers") as new_mock:
            data_to_db.aoi_geospatial_layers_data_to_db(conn, aoi, 2193)
        non_intersection.assert_called_once_with(conn, aoi, "layer_b")
        return conn, remainder, check_exists, existing_mock, new_mock

    def test_existing_table_appends_uncovered_area(self):
        conn, remainder, _, existing_mock, new_mock = self._run(table_exists=True)
        existing_mock.assert_called_once_with(conn, "LINZ", 3, "layer_b", "id", remainder, 2193)
        new_mock.assert_not_called()

    def test_missing_table_is_created_from_uncovered_area(self):
        conn, remainder, _, existing_mock, new_mock = self._run(table_exists=False)
        new_mock.assert_called_once_with(conn, "LINZ", 3, "layer_b", remainder, 2193)
        existing_mock.assert_not_called()

    def test_unknown_provider_is_skipped(self):
        with self.assertLogs(data_to_db.log, "ERROR") as logs:
            _, _, check_exists, existing_mock, new_mock = self._run(table_exists=True, data_provider="nope")
        self.assertIn("'nope'", logs.output[0])
        check_exists.assert_not_called()
        existing_mock.assert_not_called()
        new_mock.assert_not_called()

    def test_fully_covered_area_fetches_nothing(self):
        _, _, check_exists, existing_mock, new_mock = self._run(table_exists=True, covered=True)
        check_exists.assert_not_called()
        existing_mock.assert_not_called()
        new_mock.assert_not_called()


class ProviderDispatchTest(unittest.TestCase):
    """Tests that a 'full' layer is fetched with the provider registered under its 'data_provider'."""

    def _run(self, *data_providers):
        layers_df = pd.DataFrame([{
            "data_provider": data_provider, "layer_id": f"https://example.com/wfs/{i}", "table_name": f"layer_{i}",
            "unique_column_name": None, "cache_length": None, "refresh_after": pd.NaT,
        } for i, data_provider in enumerate(data_providers)])
        conn = mock.MagicMock()
        fake = mock.MagicMock(return_value=gpd.GeoDataFrame(geometry=[shapely.Point(0, 0)], crs=32759))
        with mock.patch.dict(provider_registry._PROVIDERS, {"acme": fake}, clear=True), \
            mock.patch.object(data_to_db, "get_full_geospatial_layers", return_value=layers_df), \
            mock.patch.object(data_to_db, "check_table_exists", return_value=False), \
            mock.patch.object(data_to_db, "update_full_layer_cache_expiry") as update_mock, \
            mock.patch.object(data_to_db, "gs"), \
            mock.patch.object(gpd.GeoDataFrame, "to_postgis", autospec=True) as to_postgis:
            data_to_db.full_geospatial_layers_data_to_db(conn, 32759)
        return fake, to_postgis, update_mock

    def test_uses_registered_provider(self):
        fake, to_postgis, _ = self._run("acme")
        fake.assert_called_once_with("https://example.com/wfs/0", None, 32759)
        self.assertIs(to_postgis.call_args.args[0], fake.return_value)

    def test_unknown_provider_is_skipped_and_logged(self):
        with self.assertLogs(data_to_db.log, "ERROR") as logs:
            fake, to_postgis, update_mock = self._run("nope")
        self.assertIn("'nope'", logs.output[0])
        self.assertIn("acme", logs.output[0], msg="The error should list the registered providers.")
        fake.assert_not_called()
        to_postgis.assert_not_called()
        update_mock.assert_not_called()

    def test_unknown_provider_does_not_block_later_layers(self):
        fake, to_postgis, update_mock = self._run("nope", "acme")
        fake.assert_called_once_with("https://example.com/wfs/1", None, 32759)
        self.assertEqual("layer_1", to_postgis.call_args.args[1])
        update_mock.assert_called_once_with(mock.ANY, "acme", "https://example.com/wfs/1", None)


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
        self.assertIn("refresh_after IS NULL OR refresh_after > now()", str(query))

    @mock.patch.object(data_to_db, "create_user_log_table")
    def test_nothing_logged_returns_area_of_interest(self, _):
        aoi = gpd.GeoDataFrame(geometry=[shapely.box(0, 0, 1, 1)], crs=4326)
        empty = gpd.GeoDataFrame(geometry=[], crs=4326)
        with mock.patch.object(gpd.GeoDataFrame, "from_postgis", return_value=empty):
            result = data_to_db.get_non_intersection_area_from_db(mock.MagicMock(), aoi, "layer")
        self.assertIs(result, aoi)


def _box_in_crs(lon: float, lat: float, crs: int, size: float = 1000) -> gpd.GeoDataFrame:
    """A small square AOI of side 'size' metres, built natively in 'crs' at the given location."""
    corner = gpd.GeoSeries([shapely.Point(lon, lat)], crs=4326).to_crs(crs)[0]
    return gpd.GeoDataFrame(geometry=[shapely.box(corner.x, corner.y, corner.x + size, corner.y + size)], crs=crs)


# A north/east CRS (2193), an east/north one (32759) and a polar one (3031), each with a location valid in it
AOI_LOCATIONS = {2193: (172.62, -43.54), 32759: (172.62, -43.54), 3031: (166.77, -77.85)}


class UserLogInfoRefreshAfterTest(unittest.TestCase):
    """Tests that user_log_info_to_db computes 'refresh_after' from the soonest aoi layer 'cache_length'."""

    def _run(self, cache_lengths, area_of_interest=None):
        aoi_layers = pd.DataFrame({
            "table_name": [f"t{i}" for i in range(len(cache_lengths))],
            "cache_length": cache_lengths,
        })
        if area_of_interest is None:
            area_of_interest = gpd.GeoDataFrame(geometry=[shapely.box(0, 0, 1, 1)], crs=4326)
        conn = mock.MagicMock()
        fixed_now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with mock.patch.object(data_to_db, "create_user_log_table"), \
            mock.patch.object(data_to_db, "get_aoi_geospatial_layers", return_value=aoi_layers), \
            mock.patch.object(data_to_db, "insert") as insert_mock, \
            mock.patch.object(data_to_db, "datetime") as datetime_mock:
            datetime_mock.now.return_value = fixed_now
            data_to_db.user_log_info_to_db(conn, area_of_interest)
        return insert_mock.return_value.values.call_args.kwargs, fixed_now

    def test_uses_soonest_cache_length(self):
        values, fixed_now = self._run(["1w", "2d", None])
        self.assertEqual(values["refresh_after"], fixed_now + pd.Timedelta(days=2))

    def test_none_when_no_cache_length_configured(self):
        values, _ = self._run([None, None])
        self.assertIsNone(values["refresh_after"])

    def test_geometry_stored_in_4326_round_trips(self):
        for crs, (lon, lat) in AOI_LOCATIONS.items():
            with self.subTest(crs=crs):
                aoi = _box_in_crs(lon, lat, crs)
                values, _ = self._run(["1d"], area_of_interest=aoi)
                stored = gpd.GeoDataFrame(geometry=[shapely.from_wkt(values["geometry"])], crs=4326)
                self.assertTrue(stored.to_crs(crs).geometry[0].equals_exact(aoi.geometry[0], 1e-3))


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

    @staticmethod
    def _non_intersection(aoi, logged_geometry_wkt):
        # What user_log_info_to_db stored, read back from the database
        logged = gpd.GeoDataFrame(geometry=[shapely.from_wkt(logged_geometry_wkt)], crs=4326)
        with mock.patch.object(data_to_db, "create_user_log_table"), \
            mock.patch.object(gpd.GeoDataFrame, "from_postgis", return_value=logged) as from_postgis:
            result = data_to_db.get_non_intersection_area_from_db(mock.MagicMock(), aoi, "layer")
        return result, from_postgis.call_args.args[0].compile().params

    def test_same_area_is_covered_in_any_crs(self):
        for crs, (lon, lat) in AOI_LOCATIONS.items():
            with self.subTest(crs=crs):
                aoi = _box_in_crs(lon, lat, crs)
                with self.assertRaises(data_to_db.NoNonIntersectionError):
                    self._non_intersection(aoi, aoi.to_crs(4326).geometry[0].wkt)

    def test_partial_overlap_returned_in_aoi_crs(self):
        for crs, (lon, lat) in AOI_LOCATIONS.items():
            with self.subTest(crs=crs):
                aoi = _box_in_crs(lon, lat, crs)
                minx, miny, maxx, maxy = aoi.total_bounds
                left_half = gpd.GeoSeries([shapely.box(minx, miny, (minx + maxx) / 2, maxy)], crs=crs)
                result, params = self._non_intersection(aoi, left_half.to_crs(4326)[0].wkt)
                # The AOI is sent to the database in the user log's CRS
                self.assertEqual(params["user_log_srid"], 4326)
                self.assertTrue(shapely.from_wkt(params["aoi_polygon"]).equals_exact(
                    aoi.to_crs(4326).geometry[0], 1e-9))
                self.assertEqual(result.crs.to_epsg(), crs)
                self.assertAlmostEqual(result.area.sum() / aoi.area.sum(), 0.5, places=3)


class CreateUserLogTableTest(unittest.TestCase):
    """Tests that create_user_log_table discards a user log stored in another SRID before creating it."""

    def _run(self, stored_srid):
        conn = mock.MagicMock()
        conn.execute.return_value.scalar.return_value = stored_srid
        with mock.patch.object(data_to_db.UserLogInfo.__table__, "drop") as drop_mock, \
            mock.patch.object(data_to_db, "create_table") as create_mock:
            data_to_db.create_user_log_table(conn)
        self.assertEqual(conn.execute.call_args.args[1], {"table_name": "user_log_information"})
        create_mock.assert_called_once_with(conn, data_to_db.UserLogInfo)
        return conn, drop_mock

    def test_other_srid_is_dropped(self):
        conn, drop_mock = self._run(2193)
        drop_mock.assert_called_once_with(bind=conn)

    def test_missing_or_4326_table_is_kept(self):
        for stored_srid in (None, 4326):
            with self.subTest(stored_srid=stored_srid):
                _, drop_mock = self._run(stored_srid)
                drop_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
