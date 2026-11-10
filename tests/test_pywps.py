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
Unit tests for `eddie.wps`: namespacing of plugin-contributed WPS process
identifiers, collision detection, and the spatial-containment opt-in that
process registration drives in `eddie.digitaltwin.caching.cache_common`.
"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from eddie import wps
from eddie.digitaltwin.caching import cache_common


def _make_process(identifier: str, supports_spatial_containment: bool = False) -> SimpleNamespace:
    """Build a minimal stand-in for a `pywps.Process` instance.

    Only the attributes `eddie.wps.build_processes` actually touches are set, so
    tests do not need a real PyWPS process (with its XML/schema machinery) to
    exercise the namespacing and cache-registration logic.
    """
    return SimpleNamespace(
        identifier=identifier,
        supports_spatial_containment=supports_spatial_containment,
    )


class TestPluginShortName(unittest.TestCase):
    """`_plugin_short_name` strips the deprecated `eddie_` import prefix, if present."""

    def test_strips_eddie_prefix(self):
        self.assertEqual(wps._plugin_short_name("eddie_otakaro"), "otakaro")

    def test_leaves_non_prefixed_name_untouched(self):
        self.assertEqual(wps._plugin_short_name("otakaro"), "otakaro")

    def test_only_strips_leading_prefix(self):
        # A package literally named 'eddie_eddie_foo' should only lose the first occurrence.
        self.assertEqual(wps._plugin_short_name("eddie_eddie_foo"), "eddie_foo")


class TestBuildProcesses(unittest.TestCase):
    """`build_processes` namespaces identifiers, detects collisions, and registers
    spatial-containment opt-ins - without needing a real PyWPS `Service` or plugins
    installed in the environment.
    """

    def setUp(self):
        # cache_common's opt-in set is process-global state; isolate each test from it.
        cache_common._spatial_containment_opt_in.clear()

    def tearDown(self):
        cache_common._spatial_containment_opt_in.clear()

    def test_namespaces_identifier_by_plugin(self):
        medusa = _make_process("medusa")
        with patch.object(wps, "discover_plugins", return_value={"eddie_otakaro": object()}), \
                patch.object(wps, "plugin_contribution", return_value=[medusa]):
            processes = wps.build_processes()

        self.assertEqual(len(processes), 1)
        self.assertEqual(processes[0].identifier, "otakaro.medusa")

    def test_namespaced_identifier_is_stable_across_plugins_without_eddie_prefix(self):
        # A plugin discovered under its bare package name namespaces the same way.
        proc = _make_process("site_suitability")
        with patch.object(wps, "discover_plugins", return_value={"smart_ideas": object()}), \
                patch.object(wps, "plugin_contribution", return_value=[proc]):
            processes = wps.build_processes()

        self.assertEqual(processes[0].identifier, "smart_ideas.site_suitability")

    def test_aggregates_processes_from_multiple_plugins(self):
        plugins = {"eddie_otakaro": object(), "eddie_fredt": object()}
        contributions = {
            "eddie_otakaro": [_make_process("medusa")],
            "eddie_fredt": [_make_process("flood_model")],
        }
        with patch.object(wps, "discover_plugins", return_value=plugins), \
                patch.object(wps, "plugin_contribution", side_effect=lambda plugin, name: contributions[
                    next(k for k, v in plugins.items() if v is plugin)
                ]):
            processes = wps.build_processes()

        identifiers = {p.identifier for p in processes}
        self.assertEqual(identifiers, {"otakaro.medusa", "fredt.flood_model"})

    def test_plugin_with_no_processes_contribution_is_skipped(self):
        with patch.object(wps, "discover_plugins", return_value={"eddie_otakaro": object()}), \
                patch.object(wps, "plugin_contribution", return_value=None):
            processes = wps.build_processes()

        self.assertEqual(processes, [])

    def test_duplicate_namespaced_identifier_raises(self):
        # Same plugin contributing two processes with the same bare identifier collide
        # once namespaced - this must fail loudly rather than silently overwrite one.
        dup_a = _make_process("medusa")
        dup_b = _make_process("medusa")
        with patch.object(wps, "discover_plugins", return_value={"eddie_otakaro": object()}), \
                patch.object(wps, "plugin_contribution", return_value=[dup_a, dup_b]):
            with self.assertRaises(RuntimeError):
                wps.build_processes()

    def test_duplicate_identifier_across_two_plugins_raises(self):
        # Two different plugins both naming a process 'medusa' under the same short
        # name is the exact collision this namespacing exists to prevent.
        plugins = {"eddie_otakaro": object(), "otakaro": object()}
        contributions = {
            "eddie_otakaro": [_make_process("medusa")],
            "otakaro": [_make_process("medusa")],
        }
        with patch.object(wps, "discover_plugins", return_value=plugins), \
                patch.object(wps, "plugin_contribution", side_effect=lambda plugin, name: contributions[
                    next(k for k, v in plugins.items() if v is plugin)
                ]):
            with self.assertRaises(RuntimeError):
                wps.build_processes()

    def test_opted_in_process_is_registered_for_spatial_containment(self):
        medusa = _make_process("medusa", supports_spatial_containment=True)
        with patch.object(wps, "discover_plugins", return_value={"eddie_otakaro": object()}), \
                patch.object(wps, "plugin_contribution", return_value=[medusa]):
            wps.build_processes()

        self.assertTrue(cache_common.supports_spatial_containment("otakaro.medusa"))

    def test_process_without_flag_is_not_registered(self):
        flood_model = _make_process("flood_model")  # supports_spatial_containment defaults False
        with patch.object(wps, "discover_plugins", return_value={"eddie_fredt": object()}), \
                patch.object(wps, "plugin_contribution", return_value=[flood_model]):
            wps.build_processes()

        self.assertFalse(cache_common.supports_spatial_containment("fredt.flood_model"))

    def test_process_without_attribute_at_all_is_not_registered(self):
        # Real pywps.Process subclasses that never set the attribute must default safely.
        bare = SimpleNamespace(identifier="site_suitability")
        with patch.object(wps, "discover_plugins", return_value={"smart_ideas": object()}), \
                patch.object(wps, "plugin_contribution", return_value=[bare]):
            wps.build_processes()

        self.assertFalse(cache_common.supports_spatial_containment("smart_ideas.site_suitability"))

    def test_registration_uses_the_namespaced_identifier_not_the_bare_one(self):
        medusa = _make_process("medusa", supports_spatial_containment=True)
        with patch.object(wps, "discover_plugins", return_value={"eddie_otakaro": object()}), \
                patch.object(wps, "plugin_contribution", return_value=[medusa]):
            wps.build_processes()

        self.assertFalse(cache_common.supports_spatial_containment("medusa"))
        self.assertTrue(cache_common.supports_spatial_containment("otakaro.medusa"))

    def test_no_plugins_discovered_returns_empty_list(self):
        with patch.object(wps, "discover_plugins", return_value={}):
            self.assertEqual(wps.build_processes(), [])


class TestBuildService(unittest.TestCase):
    """`build_service` wraps `build_processes` output in a single `pywps.Service`,
    configured from `pywps.cfg`.
    """

    def test_builds_a_single_service_from_all_processes(self):
        medusa = _make_process("medusa")
        fake_service = object()
        with patch.object(wps, "discover_plugins", return_value={"eddie_otakaro": object()}), \
                patch.object(wps, "plugin_contribution", return_value=[medusa]), \
                patch.object(wps.pywps, "Service", return_value=fake_service) as mock_service:
            result = wps.build_service()

        self.assertIs(result, fake_service)
        mock_service.assert_called_once()
        _, kwargs = mock_service.call_args
        self.assertEqual([p.identifier for p in kwargs["processes"]], ["otakaro.medusa"])
        self.assertEqual(kwargs["cfgfiles"], ["src/pywps.cfg"])


if __name__ == "__main__":
    unittest.main()
