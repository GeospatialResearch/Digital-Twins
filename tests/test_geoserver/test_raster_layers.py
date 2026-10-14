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

"""Tests for raster_layers.py."""
import pathlib
import tempfile
import unittest
from http import HTTPStatus
from unittest.mock import MagicMock, patch

import requests

from eddie.geoserver import raster_layers
from tests.test_geoserver.test_database_layers import fake_response

MODULE = "eddie.geoserver.raster_layers"


@patch(f"{MODULE}.get_geoserver_url", return_value="http://geoserver")
@patch(f"{MODULE}.delete_style")
@patch(f"{MODULE}.style_exists")
@patch(f"{MODULE}.requests")
class AddStyleTest(unittest.TestCase):
    """Tests the log message and requests made by add_style."""

    def setUp(self) -> None:
        """Create a temporary SLD file."""
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        self.style_file = pathlib.Path(tmp_dir.name) / "my_style.sld"
        self.style_file.write_text("<sld/>")

    def _add_style(self, requests_mock: MagicMock, exists_mock: MagicMock, exists: bool, replace: bool) -> str:
        """Run add_style and return the final log message."""
        exists_mock.return_value = exists
        with self.assertLogs(raster_layers.log, level="INFO") as logs:
            raster_layers.add_style(self.style_file, replace=replace)
        requests_mock.put.assert_called_once()
        return logs.records[-1].getMessage()

    def test_new_style_logs_created(
            self, requests_mock: MagicMock, exists_mock: MagicMock, _delete: MagicMock, _url: MagicMock
    ) -> None:
        """A style that did not exist is created."""
        message = self._add_style(requests_mock, exists_mock, exists=False, replace=False)
        self.assertEqual("Style 'my_style.sld' created.", message)
        requests_mock.post.assert_called_once()

    def test_existing_style_replace_logs_replaced(
            self, requests_mock: MagicMock, exists_mock: MagicMock, delete: MagicMock, _url: MagicMock
    ) -> None:
        """An existing style is deleted, recreated and logged as replaced."""
        message = self._add_style(requests_mock, exists_mock, exists=True, replace=True)
        self.assertEqual("Style 'my_style.sld' replaced.", message)
        delete.assert_called_once_with("my_style")
        requests_mock.post.assert_called_once()

    def test_existing_style_no_replace_logs_updated(
            self, requests_mock: MagicMock, exists_mock: MagicMock, delete: MagicMock, _url: MagicMock
    ) -> None:
        """An existing style is not recreated, only its SLD is updated."""
        message = self._add_style(requests_mock, exists_mock, exists=True, replace=False)
        self.assertEqual("Style 'my_style.sld' updated.", message)
        delete.assert_not_called()
        requests_mock.post.assert_not_called()


@patch(f"{MODULE}.get_geoserver_url", return_value="http://geoserver")
class RasterLayersListingTest(unittest.TestCase):
    """Tests get_workspace_raster_layers."""

    @patch(f"{MODULE}.requests.get")
    def test_not_found_is_empty(self, mock_get: MagicMock, _url: MagicMock) -> None:
        """A missing workspace has no raster layers."""
        mock_get.return_value = fake_response(HTTPStatus.NOT_FOUND)
        with self.assertLogs(raster_layers.log, level="WARNING"):
            self.assertEqual([], raster_layers.get_workspace_raster_layers("ws"))

    @patch(f"{MODULE}.requests.get")
    def test_server_error_raises(self, mock_get: MagicMock, _url: MagicMock) -> None:
        """Other error statuses still raise."""
        mock_get.return_value = fake_response(HTTPStatus.INTERNAL_SERVER_ERROR)
        with self.assertRaises(requests.HTTPError):
            raster_layers.get_workspace_raster_layers("ws")


if __name__ == '__main__':
    unittest.main()
