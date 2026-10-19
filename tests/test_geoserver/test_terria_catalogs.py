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
import unittest
from http import HTTPStatus
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
