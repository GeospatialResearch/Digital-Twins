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

"""Tests for terria_catalogs.py."""
import sys
import unittest
from http import HTTPStatus
from types import ModuleType
from unittest.mock import MagicMock, patch

from eddie.config import EnvVariable
from eddie.geoserver import terria_catalogs
from tests.test_geoserver.test_database_layers import fake_response


class TerriaCatalogTest(unittest.TestCase):
    """Tests get_terria_catalog."""

    @patch.object(EnvVariable, "EDDIE_AUTOSERVE_CATALOG", True)
    @patch("eddie.geoserver.raster_layers.get_geoserver_url", return_value="http://geoserver")
    @patch("eddie.geoserver.database_layers.get_geoserver_url", return_value="http://geoserver")
    @patch("requests.get")
    def test_empty_instance_has_empty_groups(self, mock_get: MagicMock, _db_url: MagicMock, _r_url: MagicMock) -> None:
        """When GeoServer has no workspaces or stores yet, each workspace group is empty instead of erroring."""
        mock_get.return_value = fake_response(HTTPStatus.NOT_FOUND)
        catalog = terria_catalogs.get_terria_catalog()["catalog"]
        self.assertEqual(len(terria_catalogs.Workspaces), len(catalog))
        for group in catalog:
            self.assertEqual([], group["members"])


class PluginCatalogTest(unittest.TestCase):
    """Tests merging plugin catalog() groups into get_terria_catalog."""

    PLUGIN_GROUP = {"type": "group", "name": "Plugin", "members": []}

    def setUp(self) -> None:
        """Create a fake plugin with a catalog() and one without, importable as real plugins are."""
        self.plugin = ModuleType("eddie_fake")
        self.plugin.catalog = lambda: [self.PLUGIN_GROUP]
        self.plain_plugin = ModuleType("eddie_plain")
        modules = patch.dict(sys.modules, {"eddie_fake": self.plugin, "eddie_plain": self.plain_plugin})
        modules.start()
        self.addCleanup(modules.stop)

    @patch.object(EnvVariable, "EDDIE_AUTOSERVE_CATALOG", False)
    @patch("eddie.geoserver.terria_catalogs.get_layers_as_terria_group")
    def test_flag_off_serves_only_plugin_groups(self, mock_group: MagicMock) -> None:
        """With EDDIE_AUTOSERVE_CATALOG false, GeoServer is not queried but plugin groups are still served."""
        catalog = terria_catalogs.get_terria_catalog([self.plugin])["catalog"]
        self.assertEqual([self.PLUGIN_GROUP], catalog)
        mock_group.assert_not_called()

    @patch.object(EnvVariable, "EDDIE_AUTOSERVE_CATALOG", True)
    @patch("eddie.geoserver.terria_catalogs.get_layers_as_terria_group", side_effect=lambda ws: ws)
    def test_flag_on_serves_plugin_then_geoserver_groups(self, _group: MagicMock) -> None:
        """With EDDIE_AUTOSERVE_CATALOG true, the plugin groups come first, then the GeoServer workspace groups."""
        catalog = terria_catalogs.get_terria_catalog([self.plugin])["catalog"]
        self.assertEqual([self.PLUGIN_GROUP, *terria_catalogs.Workspaces], catalog)

    @patch.object(EnvVariable, "EDDIE_AUTOSERVE_CATALOG", False)
    def test_plugin_without_catalog_skipped(self) -> None:
        """A plugin without a catalog contribution adds no groups; a `catalog` submodule's catalog() is used."""
        submodule = ModuleType("eddie_fake.catalog")
        submodule.catalog = lambda: [self.PLUGIN_GROUP]
        self.plugin.catalog = submodule
        catalog = terria_catalogs.get_terria_catalog([self.plain_plugin, self.plugin])["catalog"]
        self.assertEqual([self.PLUGIN_GROUP], catalog)


class RasterCatalogItemTest(unittest.TestCase):
    """Tests the served CRS of raster catalogue items."""

    def test_uses_served_crs(self) -> None:
        """Web mercator is requested as is, any other served CRS is requested as EPSG:4326."""
        for served_crs, expected in (("EPSG:3857", "EPSG:3857"), ("EPSG:3031", "EPSG:4326")):
            with self.subTest(served_crs=served_crs):
                item = terria_catalogs.create_raster_layer_catalog_item("http://geoserver/ws", "lyr", served_crs)
                self.assertEqual(expected, item["crs"])

    @patch("eddie.geoserver.terria_catalogs.get_raster_layer_crs")
    @patch("eddie.geoserver.terria_catalogs.get_workspace_raster_layers", return_value=["lyr"])
    @patch("eddie.geoserver.terria_catalogs.get_workspace_vector_layers", return_value=[])
    def test_group_uses_crs_read_back_from_geoserver(
            self, _vector: MagicMock, _raster: MagicMock, mock_crs: MagicMock) -> None:
        """The catalogue member's CRS follows the CRS GeoServer reports for the layer."""
        for served_crs, expected in (("EPSG:3031", "EPSG:4326"), ("EPSG:3857", "EPSG:3857")):
            with self.subTest(served_crs=served_crs):
                mock_crs.return_value = served_crs
                group = terria_catalogs.get_layers_as_terria_group("ws")
                self.assertEqual(expected, group["members"][0]["crs"])


if __name__ == '__main__':
    unittest.main()
