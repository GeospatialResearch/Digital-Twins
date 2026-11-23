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

"""
Unit tests for the spatial-containment opt-in registry in
`eddie.digitaltwin.caching.cache_common`: `register_spatial_containment` and
`supports_spatial_containment`. These replace the old hardcoded
`SPATIAL_CONTAINMENT_OPT_IN` frozenset (PR #458) with a registry that processes
populate themselves at discovery time (see `eddie.wps.build_processes`).
"""

import threading
import unittest

from eddie.digitaltwin.caching import cache_common


class TestSpatialContainmentRegistry(unittest.TestCase):
    """Behaviour of the registration/lookup pair in isolation from WPS process
    discovery, which is covered separately in `tests/test_wps.py`.
    """

    def setUp(self):
        # Module-level state shared across the process; reset it so tests are
        # independent of registration order / leftover state from other tests.
        cache_common._spatial_containment_opt_in.clear()

    def tearDown(self):
        cache_common._spatial_containment_opt_in.clear()

    def test_unregistered_process_does_not_support_containment(self):
        self.assertFalse(cache_common.supports_spatial_containment("otakaro.medusa"))

    def test_registered_process_supports_containment(self):
        cache_common.register_spatial_containment("otakaro.medusa")
        self.assertTrue(cache_common.supports_spatial_containment("otakaro.medusa"))

    def test_registration_is_scoped_to_its_own_process_id(self):
        cache_common.register_spatial_containment("otakaro.medusa")
        self.assertFalse(cache_common.supports_spatial_containment("fredt.flood_model"))

    def test_registration_is_idempotent(self):
        cache_common.register_spatial_containment("otakaro.medusa")
        cache_common.register_spatial_containment("otakaro.medusa")
        self.assertEqual(
            sum(1 for p in cache_common._spatial_containment_opt_in if p == "otakaro.medusa"),
            1,
        )

    def test_multiple_processes_can_be_registered_independently(self):
        cache_common.register_spatial_containment("otakaro.medusa")
        cache_common.register_spatial_containment("fredt.flood_model")

        self.assertTrue(cache_common.supports_spatial_containment("otakaro.medusa"))
        self.assertTrue(cache_common.supports_spatial_containment("fredt.flood_model"))
        self.assertFalse(cache_common.supports_spatial_containment("smart_ideas.site_suitability"))

    def test_lookup_is_exact_match_not_prefix_or_substring(self):
        # A process namespaced 'otakaro.medusa' must not make 'otakaro.medusa_v2' or
        # 'medusa' match - identifiers are opaque strings, not a hierarchy to walk.
        cache_common.register_spatial_containment("otakaro.medusa")

        self.assertFalse(cache_common.supports_spatial_containment("otakaro.medusa_v2"))
        self.assertFalse(cache_common.supports_spatial_containment("medusa"))
        self.assertFalse(cache_common.supports_spatial_containment("otakaro"))

    def test_empty_string_process_id_is_not_implicitly_registered(self):
        self.assertFalse(cache_common.supports_spatial_containment(""))

    def test_registration_from_many_threads_is_not_lost(self):
        # register_spatial_containment runs during plugin discovery, which this test
        # treats as potentially concurrent; the lock must prevent lost updates.
        process_ids = [f"plugin{i}.process" for i in range(50)]

        threads = [
            threading.Thread(target=cache_common.register_spatial_containment, args=(pid,))
            for pid in process_ids
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        for pid in process_ids:
            self.assertTrue(cache_common.supports_spatial_containment(pid))


if __name__ == "__main__":
    unittest.main()
