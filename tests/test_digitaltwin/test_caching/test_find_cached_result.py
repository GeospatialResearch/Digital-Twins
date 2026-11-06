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

"""Tests for find_cached_result.py"""
import collections
import unittest
from types import SimpleNamespace
from unittest import mock

import geopandas as gpd
import pytest
import shapely
from shapely import wkt

from eddie.digitaltwin.caching import cache_common
from eddie.digitaltwin.caching import find_cached_result as find_module

Row = collections.namedtuple("Row", ["output_id"])

# Christchurch, in 4326 and in NZTM (2193).
CHCH_4326 = shapely.box(172.62, -43.54, 172.63, -43.53)
CHCH_2193 = gpd.GeoSeries([CHCH_4326], crs=4326).to_crs(2193).iloc[0]


def _run(process_id="fredt.flood_model", params=None, aoi=None, input_version=None, row=None, table_exists=True,
         patch_model=True):
    """Call find_cached_result against a mocked database; return (result, query, conn, check_mock)."""
    conn = mock.MagicMock()
    conn.execute.return_value.fetchone.return_value = row
    engine = mock.MagicMock()
    engine.connect.return_value.__enter__.return_value = conn
    # BUG workaround: find_cached_result reads ProcessCache.name, which a declarative model doesn't have, so every
    # call crashes with AttributeError. Stand in a model that has both, so the other branches can be tested.
    # Remove this (and patch_model) once the source uses ProcessCache.__tablename__.
    model = SimpleNamespace(name="process_cache", __tablename__="process_cache") if patch_model \
        else cache_common.ProcessCache
    with mock.patch.object(find_module.setup_environment, "get_database", return_value=engine), \
         mock.patch.object(find_module, "check_table_exists", return_value=table_exists) as check_mock, \
         mock.patch.object(find_module, "ProcessCache", model):
        result = find_module.find_cached_result(process_id, {"depth": 7} if params is None else params, aoi,
                                                input_version)
    query = conn.execute.call_args.args[0] if conn.execute.called else None
    return result, query, conn, check_mock


class FindCachedResultTest(unittest.TestCase):
    """Tests for find_cached_result."""

    def test_binds_process_id_so_processes_are_isolated(self):
        _, query_a, _, _ = _run(process_id="fredt.flood_model", params={"depth": 7})
        _, query_b, _, _ = _run(process_id="smart_ideas.site_suitability", params={"depth": 7})
        params_a, params_b = query_a.compile().params, query_b.compile().params
        self.assertEqual(params_a["params_hash"], params_b["params_hash"])
        self.assertEqual(params_a["process_id"], "fredt.flood_model")
        self.assertEqual(params_b["process_id"], "smart_ideas.site_suitability")
        self.assertIn("process_id = :process_id", str(query_a))

    def test_binds_hash_of_canonical_parameters(self):
        _, query_a, _, _ = _run(params={"rain": 120, "depth": 7})
        _, query_b, _, _ = _run(params={"depth": 7, "rain": 120})
        self.assertEqual(query_a.compile().params["params_hash"],
                         cache_common.compute_params_hash({"depth": 7, "rain": 120}))
        self.assertEqual(query_a.compile().params["params_hash"], query_b.compile().params["params_hash"])
        self.assertIn("params_hash = :params_hash", str(query_a))

    def test_queries_process_cache_table_newest_first(self):
        _, query, conn, check_mock = _run()
        check_mock.assert_called_once_with(conn, "process_cache")
        sql = str(query)
        self.assertIn("FROM process_cache", sql)
        self.assertIn("ORDER BY created_at DESC", sql)
        self.assertIn("LIMIT 1", sql)

    def test_missing_table_returns_none_without_querying(self):
        result, _, conn, _ = _run(table_exists=False)
        self.assertIsNone(result)
        conn.execute.assert_not_called()

    def test_no_aoi_matches_only_null_aoi(self):
        _, query, _, _ = _run(aoi=None)
        sql = str(query)
        self.assertIn("aoi IS NULL", sql)
        self.assertNotIn("ST_Equals", sql)
        self.assertNotIn("ST_Contains", sql)
        self.assertNotIn("aoi_wkt", query.compile().params)

    def test_aoi_requires_exact_match_without_opt_in(self):
        aoi = gpd.GeoDataFrame(geometry=[CHCH_4326], crs=4326)
        _, query, _, _ = _run(aoi=aoi)
        sql = str(query)
        self.assertIn("ST_Equals(aoi, ST_SetSRID(ST_GeomFromText(:aoi_wkt), 4326))", sql)
        self.assertNotIn("ST_Contains", sql)
        self.assertNotIn("aoi IS NULL", sql)
        self.assertEqual(query.compile().params["aoi_wkt"], CHCH_4326.wkt)

    def test_aoi_uses_containment_when_opted_in(self):
        aoi = gpd.GeoDataFrame(geometry=[CHCH_4326], crs=4326)
        with mock.patch.object(cache_common, "_spatial_containment_opt_in", {"fredt.flood_model"}):
            _, query, _, _ = _run(process_id="fredt.flood_model", aoi=aoi)
        sql = str(query)
        self.assertIn("ST_Contains(aoi, ST_SetSRID(ST_GeomFromText(:aoi_wkt), 4326))", sql)
        self.assertNotIn("ST_Equals", sql)
        self.assertEqual(query.compile().params["aoi_wkt"], CHCH_4326.wkt)

    def test_other_process_still_exact_when_one_is_opted_in(self):
        aoi = gpd.GeoDataFrame(geometry=[CHCH_4326], crs=4326)
        with mock.patch.object(cache_common, "_spatial_containment_opt_in", {"fredt.flood_model"}):
            _, query, _, _ = _run(process_id="smart_ideas.site_suitability", aoi=aoi)
        self.assertIn("ST_Equals", str(query))
        self.assertNotIn("ST_Contains", str(query))

    def test_input_version_is_canonicalised_and_bound(self):
        _, query, _, _ = _run(input_version={"dataset_ids": {"lidar": "nz-lidar-2024-v3", "dem": "v2"}, "a": 1})
        sql = str(query)
        self.assertIn("input_version::jsonb = cast(:input_version as jsonb)", sql)
        self.assertNotIn("input_version IS NULL", sql)
        self.assertEqual(query.compile().params["input_version"],
                         '{"a":1,"dataset_ids":{"dem":"v2","lidar":"nz-lidar-2024-v3"}}')

    def test_no_input_version_matches_only_null_input_version(self):
        _, query, _, _ = _run(input_version=None)
        self.assertIn("input_version IS NULL", str(query))
        self.assertNotIn("input_version", query.compile().params)

    def test_miss_returns_none(self):
        result, _, conn, _ = _run(row=None)
        self.assertIsNone(result)
        conn.execute.assert_called_once()

    @pytest.mark.xfail(raises=AttributeError, strict=True,
                       reason="BUG: hit reads row.id but the query only selects output_id. Remove when fixed.")
    def test_hit_returns_output_id(self):
        result, _, _, _ = _run(row=Row("job-42"))
        self.assertEqual(result, "job-42")

    @pytest.mark.xfail(raises=AttributeError, strict=True,
                       reason="BUG: ProcessCache.name doesn't exist on the declarative model; use __tablename__. "
                              "Remove when fixed.")
    def test_does_not_crash_on_real_table_model(self):
        result, query, conn, check_mock = _run(patch_model=False)
        self.assertIsNone(result)
        check_mock.assert_called_once_with(conn, "process_cache")
        self.assertIn("FROM process_cache", str(query))

    @pytest.mark.xfail(raises=AssertionError, strict=True,
                       reason="BUG: AOI WKT is labelled SRID 4326 without to_crs(4326), so NZTM AOIs never match. "
                              "Remove when fixed.")
    def test_aoi_is_reprojected_to_4326(self):
        aoi = gpd.GeoDataFrame(geometry=[CHCH_2193], crs=2193)
        _, query, _, _ = _run(aoi=aoi)
        bound = wkt.loads(query.compile().params["aoi_wkt"])
        self.assertTrue(bound.equals_exact(CHCH_4326, 1e-6), msg=bound.wkt)


if __name__ == "__main__":
    unittest.main()
