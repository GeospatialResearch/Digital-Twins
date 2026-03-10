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

from eddie import discover_plugins


class DiscoverPluginsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Ensure test modules are accessible
        sys.path.append(str(pathlib.Path(__file__).parent.resolve()))

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


if __name__ == '__main__':
    unittest.main()
