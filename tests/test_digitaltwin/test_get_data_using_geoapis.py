"""Tests for get_data_using_geoapis.py"""
import unittest
from unittest import mock

import geopandas as gpd
import shapely

from eddie.digitaltwin import get_data_using_geoapis, nz_providers, provider_registry

AOI_4326 = gpd.GeoDataFrame(geometry=[shapely.box(172.62, -43.54, 172.65, -43.52)], crs=4326)


@mock.patch.object(nz_providers, "StatsNz")
class FetchCrsTest(unittest.TestCase):
    """Tests that data is fetched in the requested CRS when geoapis can query in it, else in EPSG:4326."""

    def fetch(self, stats_nz: mock.Mock, crs: int, fetched: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        stats_nz.return_value.run.return_value = fetched
        provider = provider_registry.get_provider("StatsNZ")
        return provider(1, AOI_4326.to_crs(crs), crs)

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


class CleanFetchedVectorDataTest(unittest.TestCase):
    """Tests for clean_fetched_vector_data."""

    def test_lowercases_column_names(self):
        gdf = gpd.GeoDataFrame({"ID": [1], "Name": ["a"]}, geometry=[shapely.Point(0, 0)])
        cleaned = get_data_using_geoapis.clean_fetched_vector_data(gdf)
        self.assertEqual(list(cleaned.columns), ["id", "name", "geometry"])

    def test_moves_geometry_column_to_end(self):
        gdf = gpd.GeoDataFrame({"geometry": [shapely.Point(0, 0)], "id": [1]})
        gdf = gdf.set_geometry("geometry")
        cleaned = get_data_using_geoapis.clean_fetched_vector_data(gdf)
        self.assertEqual(list(cleaned.columns)[-1], "geometry")

    def test_preserves_crs(self):
        gdf = gpd.GeoDataFrame({"ID": [1]}, geometry=[shapely.Point(0, 0)], crs=4326)
        cleaned = get_data_using_geoapis.clean_fetched_vector_data(gdf)
        self.assertEqual(cleaned.crs.to_epsg(), 4326)


class ResolveWfsFetchCrsTest(unittest.TestCase):
    """Tests for resolve_wfs_fetch_crs."""

    def test_north_east_crs_is_kept(self):
        # EPSG:4326 (WGS84) has axis order (north, east)
        self.assertEqual(get_data_using_geoapis.resolve_wfs_fetch_crs(4326), 4326)

    def test_nztm_crs_is_kept(self):
        # EPSG:2193 (NZTM2000) has axis order (north, east)
        self.assertEqual(get_data_using_geoapis.resolve_wfs_fetch_crs(2193), 2193)

    def test_utm_crs_falls_back_to_4326(self):
        # EPSG:32759 (UTM zone 59S) has axis order (east, north)
        self.assertEqual(get_data_using_geoapis.resolve_wfs_fetch_crs(32759), 4326)


class FetchVectorDataUsingGeoapisTest(unittest.TestCase):
    """Tests for fetch_vector_data_using_geoapis."""

    def test_cleans_and_reprojects_returned_data(self):
        fetched = gpd.GeoDataFrame({"ID": [1]}, geometry=[shapely.Point(174.76, -36.85)], crs=4326)
        fetcher = mock.MagicMock()
        fetcher.run.return_value = fetched
        result = get_data_using_geoapis.fetch_vector_data_using_geoapis(fetcher, "layer", 2193)
        fetcher.run.assert_called_once_with("layer")
        self.assertEqual(result.crs.to_epsg(), 2193)
        self.assertEqual(list(result.columns), ["id", "geometry"])

    def test_returns_empty_geodataframe_when_fetcher_returns_none(self):
        fetcher = mock.MagicMock()
        fetcher.run.return_value = None
        result = get_data_using_geoapis.fetch_vector_data_using_geoapis(fetcher, "layer", 4326)
        self.assertIsInstance(result, gpd.GeoDataFrame)
        self.assertTrue(result.empty)

    def test_returns_empty_geodataframe_when_fetcher_returns_non_geodataframe(self):
        fetcher = mock.MagicMock()
        fetcher.run.return_value = "not a geodataframe"
        result = get_data_using_geoapis.fetch_vector_data_using_geoapis(fetcher, "layer", 4326)
        self.assertIsInstance(result, gpd.GeoDataFrame)
        self.assertTrue(result.empty)


class FetchGenericWfsDataTest(unittest.TestCase):
    """Tests for fetch_generic_wfs_data."""

    def _run(self, url, bbox=None, crs=4326, fetched=None):
        fetched = fetched if fetched is not None else gpd.GeoDataFrame(
            {"ID": [1]}, geometry=[shapely.Point(0, 0)], crs=crs)
        with mock.patch.object(get_data_using_geoapis, "WfsQuery") as wfs_query_cls:
            wfs_query_cls.return_value.run.return_value = fetched
            result = get_data_using_geoapis.fetch_generic_wfs_data(url, bbox, crs)
        return result, wfs_query_cls

    def test_raises_value_error_when_no_type_names_param(self):
        with self.assertRaises(ValueError):
            get_data_using_geoapis.fetch_generic_wfs_data(
                "https://example.com/geoserver/wfs?service=WFS&request=GetFeature", None, 4326)

    def test_parses_type_names_and_netloc(self):
        url = "https://example.com/geoserver/wfs?service=WFS&request=GetFeature&typeNames=ns:layer"
        _, wfs_query_cls = self._run(url)
        wfs_query_cls.assert_called_once()
        kwargs = wfs_query_cls.call_args.kwargs
        self.assertEqual(kwargs["netloc_url"], "example.com")
        self.assertIsNone(kwargs["bounding_polygon"])
        wfs_query_cls.return_value.run.assert_called_once_with("ns:layer")

    def test_accepts_type_name_singular_param(self):
        url = "https://example.com/geoserver/wfs?typeName=ns:layer"
        _, wfs_query_cls = self._run(url)
        wfs_query_cls.return_value.run.assert_called_once_with("ns:layer")

    def test_passes_bbox_as_bounding_polygon(self):
        url = "https://example.com/geoserver/wfs?typeNames=ns:layer"
        bbox = gpd.GeoDataFrame(geometry=[shapely.box(0, 0, 1, 1)], crs=4326)
        _, wfs_query_cls = self._run(url, bbox=bbox, crs=4326)
        kwargs = wfs_query_cls.call_args.kwargs
        self.assertIsNotNone(kwargs["bounding_polygon"])

    def test_result_reprojected_to_requested_crs(self):
        url = "https://example.com/geoserver/wfs?typeNames=ns:layer"
        fetched = gpd.GeoDataFrame({"ID": [1]}, geometry=[shapely.Point(174.76, -36.85)], crs=4326)
        result, _ = self._run(url, crs=2193, fetched=fetched)
        self.assertEqual(result.crs.to_epsg(), 2193)

    def test_utm_crs_fetches_in_4326_then_reprojects(self):
        url = "https://example.com/geoserver/wfs?typeNames=ns:layer"
        fetched = gpd.GeoDataFrame({"ID": [1]}, geometry=[shapely.Point(174.76, -36.85)], crs=4326)
        result, wfs_query_cls = self._run(url, crs=32759, fetched=fetched)
        self.assertEqual(wfs_query_cls.call_args.kwargs["crs"], 4326)
        self.assertEqual(result.crs.to_epsg(), 32759)


if __name__ == "__main__":
    unittest.main()
