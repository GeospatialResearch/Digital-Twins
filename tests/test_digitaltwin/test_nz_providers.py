"""Tests for nz_providers.py"""
import unittest
from unittest import mock

import geopandas as gpd
import shapely

from eddie.digitaltwin import nz_providers
from eddie.digitaltwin.provider_registry import get_provider


class MakeNzProviderTest(unittest.TestCase):
    """Tests for _make_nz_provider.

    The fetcher class (StatsNz/Linz/MFE) is deliberately re-looked-up by name inside the returned 'provider'
    closure on every call, rather than captured once into a dict at import time - so that mock.patch.object(
    nz_providers, "StatsNz") etc. (as used below and by FetchCrsTest) takes effect even on providers that were
    already built/registered before the patch was applied. These tests patch 'StatsNz' itself (not a fake dict
    entry) to exercise that exact mechanism and guard against regressing back to an import-time-bound dict.
    """

    def test_raises_for_unsupported_provider_name(self):
        with self.assertRaises(ValueError):
            nz_providers._make_nz_provider("NotAProvider")

    @mock.patch.object(nz_providers, "fetch_vector_data_using_geoapis")
    @mock.patch.object(nz_providers, "StatsNz")
    def test_constructs_fetcher_with_api_key_and_crs(self, stats_nz, fetch_vector_data):
        provider = nz_providers._make_nz_provider("StatsNZ")
        provider("123", None, 4326)
        stats_nz.assert_called_once_with(
            key=nz_providers._NZ_PROVIDER_KEYS["StatsNZ"], crs=4326, bounding_polygon=None, verbose=False)

    @mock.patch.object(nz_providers, "fetch_vector_data_using_geoapis")
    @mock.patch.object(nz_providers, "StatsNz")
    def test_no_bbox_means_no_bounding_polygon(self, stats_nz, fetch_vector_data):
        provider = nz_providers._make_nz_provider("StatsNZ")
        provider("123", None, 2193)
        self.assertIsNone(stats_nz.call_args.kwargs["bounding_polygon"])

    @mock.patch.object(nz_providers, "fetch_vector_data_using_geoapis")
    @mock.patch.object(nz_providers, "StatsNz")
    def test_bbox_is_reprojected_to_fetch_crs_and_passed_through(self, stats_nz, fetch_vector_data):
        provider = nz_providers._make_nz_provider("StatsNZ")
        bbox = gpd.GeoDataFrame(geometry=[shapely.box(0, 0, 1, 1)], crs=4326)
        provider("123", bbox, 2193)
        bounding_polygon = stats_nz.call_args.kwargs["bounding_polygon"]
        self.assertEqual(bounding_polygon.crs.to_epsg(), 2193)

    @mock.patch.object(nz_providers, "fetch_vector_data_using_geoapis")
    @mock.patch.object(nz_providers, "StatsNz")
    def test_layer_id_is_passed_as_int(self, stats_nz, fetch_vector_data):
        provider = nz_providers._make_nz_provider("StatsNZ")
        provider("456", None, 4326)
        fetch_vector_data.assert_called_once_with(stats_nz.return_value, 456, 4326)

    @mock.patch.object(nz_providers, "fetch_vector_data_using_geoapis")
    @mock.patch.object(nz_providers, "StatsNz")
    def test_returns_fetch_vector_data_result(self, stats_nz, fetch_vector_data):
        expected = gpd.GeoDataFrame({"id": [1]}, geometry=[shapely.Point(0, 0)], crs=4326)
        fetch_vector_data.return_value = expected
        provider = nz_providers._make_nz_provider("StatsNZ")
        result = provider("123", None, 4326)
        self.assertIs(result, expected)


@mock.patch.object(nz_providers, "StatsNz")
class FetchCrsTest(unittest.TestCase):
    """Tests that data is fetched in the requested CRS when geoapis can query in it, else in EPSG:4326.

    Regression test for the registry-callable split: StatsNZ's provider is built once at module-import time (via
    'register_provider' at the bottom of nz_providers.py), before this patch is applied, so this also confirms
    the already-registered provider still picks up a later mock.patch.object(nz_providers, "StatsNz").
    """

    def fetch(self, stats_nz: mock.Mock, crs: int, fetched: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        stats_nz.return_value.run.return_value = fetched
        provider = get_provider("StatsNZ")
        aoi_4326 = gpd.GeoDataFrame(geometry=[shapely.box(172.62, -43.54, 172.65, -43.52)], crs=4326)
        return provider("1", aoi_4326.to_crs(crs), crs)

    def test_north_east_crs_fetched_directly(self, stats_nz):
        fetched = gpd.GeoDataFrame({"ID": [1]}, crs=2193, geometry=[shapely.Point(1570000, 5180000)])
        result = self.fetch(stats_nz, 2193, fetched)
        self.assertEqual(stats_nz.call_args.kwargs["crs"], 2193)
        self.assertEqual(stats_nz.call_args.kwargs["bounding_polygon"].crs.to_epsg(), 2193)
        self.assertEqual(result.crs.to_epsg(), 2193)
        self.assertEqual(list(result.columns), ["id", "geometry"])

    def test_other_crs_fetched_in_4326(self, stats_nz):
        for crs in (32759, 3031):
            fetched = gpd.GeoDataFrame({"ID": [1]}, crs=4326, geometry=[shapely.Point(172.63, -43.53)])
            result = self.fetch(stats_nz, crs, fetched)
            self.assertEqual(stats_nz.call_args.kwargs["crs"], 4326)
            self.assertEqual(stats_nz.call_args.kwargs["bounding_polygon"].crs.to_epsg(), 4326)
            self.assertEqual(result.crs.to_epsg(), crs)


class NzProvidersRegisteredOnImportTest(unittest.TestCase):
    """Tests that importing nz_providers registers the NZ-specific providers in the shared registry."""

    def test_statsnz_registered(self):
        from eddie.digitaltwin.provider_registry import registered_providers
        self.assertIn("StatsNZ", registered_providers())

    def test_linz_registered(self):
        from eddie.digitaltwin.provider_registry import registered_providers
        self.assertIn("LINZ", registered_providers())

    def test_mfe_registered(self):
        from eddie.digitaltwin.provider_registry import registered_providers
        self.assertIn("MFE", registered_providers())


if __name__ == "__main__":
    unittest.main()
