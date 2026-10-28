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

"""Test cases for the eddie.discover_plugins module"""

import pathlib
import sys
import unittest
from importlib.metadata import EntryPoint
from unittest import mock

from eddie import discover_plugins


def ep(name: str, module: str) -> EntryPoint:
    """Make an "eddie.plugins" entry point."""
    return EntryPoint(name, module, discover_plugins.ENTRY_POINT_GROUP)


class DiscoverPluginsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Ensure test modules are accessible
        path = str(pathlib.Path(__file__).parent.resolve())
        sys.path.append(path)
        cls.addClassCleanup(sys.path.remove, path)

    def setUp(self):
        patcher = mock.patch("eddie.discover_plugins.entry_points", return_value=[])
        self.entry_points = patcher.start()
        self.addCleanup(patcher.stop)

    def test_discover_mock_plugin_name_exists(self):
        plugins = discover_plugins.discover_plugins()
        mock_plugin_name = "eddie_mock_plugin"
        self.assertIn(mock_plugin_name, plugins)

    def test_discover_mock_plugin_non_existent_name_does_not_exist(self):
        plugins = discover_plugins.discover_plugins()
        non_existant_mock_plugin = "eddie_non_existant_mock_plugin"
        self.assertNotIn(non_existant_mock_plugin, plugins)

    def test_discover_builtin_does_not_exist(self):
        plugins = discover_plugins.discover_plugins()
        builtin_module = "math"
        self.assertNotIn(builtin_module, plugins)

    def test_discover_non_eddie_does_not_exist(self):
        plugins = discover_plugins.discover_plugins()
        non_eddie_module = "non_eddie_mock_plugin"
        self.assertNotIn(non_eddie_module, plugins)

    def test_discover_mock_plugin_module_signature_correct(self):
        from tests.test_discover_plugins import eddie_mock_plugin

        plugins = discover_plugins.discover_plugins()
        imported_name = eddie_mock_plugin.__name__.split(".")[-1]
        self.assertEqual(eddie_mock_plugin.__file__, plugins[imported_name].__file__)

    def test_entry_point_discovers_non_prefixed_module(self):
        self.entry_points.return_value = [ep("mock", "non_eddie_mock_plugin")]
        self.assertIn("non_eddie_mock_plugin", discover_plugins.discover_plugins())

    def test_co_installed_plugins_discovered_together(self):
        self.entry_points.return_value = [ep("a", "eddie_mock_plugin"), ep("b", "non_eddie_mock_plugin")]
        plugins = discover_plugins.discover_plugins()
        self.assertLessEqual({"eddie_mock_plugin", "non_eddie_mock_plugin"} <= plugins.keys())

    def test_duplicate_plugin_name_raises(self):
        self.entry_points.return_value = [ep("dup", "eddie_mock_plugin"), ep("dup", "non_eddie_mock_plugin")]
        with self.assertRaisesRegex(RuntimeError, "dup"):
            discover_plugins.discover_plugins()

    def test_prefix_only_plugin_warns_deprecated(self):
        with self.assertLogs(discover_plugins.log, "WARNING") as logs:
            discover_plugins.discover_plugins()
        self.assertIn("eddie_mock_plugin", logs.output[0])

    def test_entry_point_wins_over_prefix(self):
        self.entry_points.return_value = [ep("mock", "eddie_mock_plugin")]
        with self.assertNoLogs(discover_plugins.log, "WARNING"):
            discover_plugins.discover_plugins()

    def test_plugin_contribution_attribute(self):
        plugin = mock.Mock(__name__="p", blueprint="bp")
        self.assertEqual("bp", discover_plugins.plugin_contribution(plugin, "blueprint"))

    def test_plugin_contribution_absent_is_none(self):
        plugin = mock.Mock(spec=[], __name__="eddie_mock_plugin")
        self.assertIsNone(discover_plugins.plugin_contribution(plugin, "blueprint"))

    def test_plugin_contribution_submodule(self):
        import xml
        self.assertEqual("xml.dom", discover_plugins.plugin_contribution(xml, "dom").__name__)


if __name__ == '__main__':
    unittest.main()
