# -*- coding: utf-8 -*-
# Copyright © 2021-2026 Geospatial Research Institute Toi Hangarau
# LICENSE: https://github.com/GeospatialResearch/Digital-Twins/blob/master/LICENSE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Tests for store_cached_result.py"""
import unittest
from unittest import mock

import geopandas as gpd
import pytest
import shapely
from shapely import wkt

from eddie.digitaltwin.caching import cache_common
from eddie.digitaltwin.caching import store_cached_result as store_module

# Christchurch, in 4326 and in UTM 59S (32759, east/north).
CHCH_4326 = shapely.box(172.62, -43.54, 172.63, -43.53)
CHCH_32759 = gpd.GeoSeries([CHCH_4326], crs=4326).to_crs(32759).iloc[0]


def _run(process_id="fredt.flood_model", params=None, output_id="job-42", aoi=None, input_version=None):
    """Call store_cached_result against a mocked database; return (result, conn, create_mock, insert_mock)."""
    conn = mock.MagicMock()
    engine = mock.MagicMock()
    engine.connect.return_value.__enter__.return_value = conn
    with mock.patch.object(store_module.setup_environment, "get_database", return_value=engine), \
         mock.patch.object(store_module, "create_table") as create_mock, \
         mock.patch.object(store_module, "insert") as insert_mock:
        result = store_module.store_cached_result(process_id, {"depth": 7} if params is None else params, output_id,
                                                  aoi, input_version)
    return result, conn, create_mock, insert_mock


class StoreCachedResultTest(unittest.TestCase):
    """Tests for store_cached_result."""

    def test_inserts_hash_and_str_output_id(self):
        params = {"rain": 120, "depth": 7}
        input_version = {"dataset_ids": {"lidar": "nz-lidar-2024-v3"}}
        result, conn, create_mock, insert_mock = _run(process_id="smart_ideas.site_suitability", params=params,
                                                      output_id=1234, input_version=input_version)
        self.assertEqual(result, 1234)
        create_mock.assert_called_once_with(conn, cache_common.ProcessCache)
        insert_mock.assert_called_once_with(cache_common.ProcessCache)
        insert_mock.return_value.values.assert_called_once_with(
            process_id="smart_ideas.site_suitability",
            params_hash=cache_common.compute_params_hash({"depth": 7, "rain": 120}),
            process_parameters=params,
            aoi=None,
            input_version=input_version,
            output_id="1234",
        )
        conn.execute.assert_called_once_with(insert_mock.return_value.values.return_value)

    def test_no_aoi_is_stored_as_null(self):
        _, _, _, insert_mock = _run(aoi=None)
        self.assertIsNone(insert_mock.return_value.values.call_args.kwargs["aoi"])
        self.assertIsNone(insert_mock.return_value.values.call_args.kwargs["input_version"])

    def test_4326_aoi_is_stored_as_ewkt(self):
        _, _, _, insert_mock = _run(aoi=gpd.GeoDataFrame(geometry=[CHCH_4326], crs=4326))
        self.assertEqual(insert_mock.return_value.values.call_args.kwargs["aoi"], f"SRID=4326;{CHCH_4326.wkt}")

    def test_commits_after_insert(self):
        _, conn, _, _ = _run()
        self.assertEqual([name for name, _, _ in conn.method_calls], ["execute", "commit"])

    @pytest.mark.xfail(raises=AssertionError, strict=True,
                       reason="BUG: AOI WKT is labelled SRID=4326 without to_crs(4326), so a UTM/NZTM AOI is stored "
                              "with projected coordinates. Remove when fixed.")
    def test_aoi_is_reprojected_to_4326(self):
        _, _, _, insert_mock = _run(aoi=gpd.GeoDataFrame(geometry=[CHCH_32759], crs=32759))
        srid, _, geom_wkt = insert_mock.return_value.values.call_args.kwargs["aoi"].partition(";")
        self.assertEqual(srid, "SRID=4326")
        self.assertTrue(wkt.loads(geom_wkt).equals_exact(CHCH_4326, 1e-6), msg=geom_wkt)


if __name__ == "__main__":
    unittest.main()
