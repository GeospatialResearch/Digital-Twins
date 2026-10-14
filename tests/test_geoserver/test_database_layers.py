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

"""Tests for database_layers.py."""
import unittest
from http import HTTPStatus
from unittest.mock import MagicMock, patch

import requests

from eddie.geoserver import database_layers

GS_URL = "http://geoserver/rest"


def fake_response(status: HTTPStatus, json_data: dict | None = None) -> MagicMock:
    """
    Build a fake requests response that raises HTTPError for error statuses.

    Parameters
    ----------
    status : HTTPStatus
        The status code of the response.
    json_data : dict | None = None
        The value returned by response.json().

    Returns
    -------
    MagicMock
        A mock of requests.Response.
    """
    response = MagicMock(spec=requests.Response, status_code=status.value, text="error text")
    response.json.return_value = json_data
    if status.value >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(response=response)
    return response


@patch("eddie.geoserver.database_layers.get_geoserver_url", return_value=GS_URL)
class VectorLayersTest(unittest.TestCase):
    """Tests get_workspace_vector_layers, create_datastore_layer and generate_metadata_elem."""

    @patch("eddie.geoserver.database_layers.requests.get")
    def test_not_found_is_empty(self, mock_get: MagicMock, _url: MagicMock) -> None:
        """A missing workspace or store has no layers, and is logged as a warning."""
        mock_get.return_value = fake_response(HTTPStatus.NOT_FOUND)
        with self.assertLogs(database_layers.log, level="WARNING"):
            self.assertEqual([], database_layers.get_workspace_vector_layers("ws"))

    @patch("eddie.geoserver.database_layers.requests.get")
    def test_server_error_raises(self, mock_get: MagicMock, _url: MagicMock) -> None:
        """Other error statuses still raise."""
        mock_get.return_value = fake_response(HTTPStatus.INTERNAL_SERVER_ERROR)
        with self.assertRaises(requests.HTTPError):
            database_layers.get_workspace_vector_layers("ws")

    @patch("eddie.geoserver.database_layers.requests.get")
    def test_empty_store_is_empty(self, mock_get: MagicMock, _url: MagicMock) -> None:
        """A store with no feature types returns an empty list."""
        mock_get.return_value = fake_response(HTTPStatus.OK, {"featureTypes": ""})
        self.assertEqual([], database_layers.get_workspace_vector_layers("ws"))

    @patch("eddie.geoserver.database_layers.requests.get")
    def test_layer_names(self, mock_get: MagicMock, _url: MagicMock) -> None:
        """Layer names are extracted from the response."""
        names = {"featureType": [{"name": "a"}, {"name": "b"}]}
        mock_get.return_value = fake_response(HTTPStatus.OK, {"featureTypes": names})
        self.assertEqual(["a", "b"], database_layers.get_workspace_vector_layers("ws"))

    @patch("eddie.geoserver.database_layers._warn_if_empty_bounds")
    @patch("eddie.geoserver.database_layers.recalculate_layer_bounds")
    @patch("eddie.geoserver.database_layers.requests.post")
    @patch("eddie.geoserver.database_layers.get_workspace_vector_layers", return_value=[])
    def test_create_layer_lets_geoserver_derive_extent(
            self, _layers: MagicMock, mock_post: MagicMock, mock_recalculate: MagicMock, mock_warn: MagicMock,
            _url: MagicMock
    ) -> None:
        """The POST has no explicit SRS or bounds but keeps the SQL view metadata, and its bounds are checked."""
        mock_post.return_value = fake_response(HTTPStatus.CREATED)
        database_layers.create_datastore_layer("ws", "store", "layer", metadata_elem="<metadata>view</metadata>")
        body = mock_post.call_args.kwargs["data"]
        for forbidden in ("nativeBoundingBox", "latLonBoundingBox", "<srs>", "2193"):
            self.assertNotIn(forbidden, body)
        self.assertIn("<name>layer</name>", body)
        self.assertIn("<metadata>view</metadata>", body)
        # GeoServer already calculates bounds on POST
        mock_recalculate.assert_not_called()
        mock_warn.assert_called_once_with("ws", "store", "layer")

    @patch("eddie.geoserver.database_layers._warn_if_empty_bounds")
    @patch("eddie.geoserver.database_layers.recalculate_layer_bounds")
    @patch("eddie.geoserver.database_layers.requests.post")
    @patch("eddie.geoserver.database_layers.get_workspace_vector_layers", return_value=["layer"])
    def test_existing_layer_bounds_recalculated(
            self, _layers: MagicMock, mock_post: MagicMock, mock_recalculate: MagicMock, mock_warn: MagicMock,
            _url: MagicMock
    ) -> None:
        """An existing layer is not created again, but its bounds are recalculated and checked."""
        database_layers.create_datastore_layer("ws", "store", "layer")
        mock_post.assert_not_called()
        mock_recalculate.assert_called_once_with("ws", "store", "layer")
        mock_warn.assert_called_once_with("ws", "store", "layer")

    def test_metadata_elem_is_keyword_only(self, _url: MagicMock) -> None:
        """Calls using the old (conn, workspace, store, layer) order fail loudly instead of misrouting arguments."""
        old_style_args = (MagicMock(), "ws", "store", "layer")
        with self.assertRaises(TypeError):
            database_layers.create_datastore_layer(*old_style_args)

    def test_generate_metadata_elem_fills_srid(self, _url: MagicMock) -> None:
        """The SQL view template receives the srid."""
        elem = database_layers.generate_metadata_elem("view", "SELECT 1", 4326)
        self.assertIn("<srid>4326</srid>", elem)
        self.assertIn("<name>view</name>", elem)


@patch("eddie.geoserver.database_layers.get_geoserver_url", return_value=GS_URL)
class LayerBoundsTest(unittest.TestCase):
    """Tests recalculate_layer_bounds and _warn_if_empty_bounds."""

    @patch("eddie.geoserver.database_layers.requests.put")
    def test_recalculate_sends_empty_feature_type(self, mock_put: MagicMock, _url: MagicMock) -> None:
        """Only the bounds are recalculated: the body is empty, so attributes and other settings are kept."""
        mock_put.return_value = fake_response(HTTPStatus.OK)
        database_layers.recalculate_layer_bounds("ws", "store", "layer")
        put = mock_put.call_args
        self.assertEqual(f"{GS_URL}/workspaces/ws/datastores/store/featuretypes/layer", put.args[0])
        self.assertEqual({"recalculate": "nativebbox,latlonbbox"}, put.kwargs["params"])
        self.assertEqual("<featureType/>", put.kwargs["data"])

    @patch("eddie.geoserver.database_layers.requests.put")
    def test_recalculate_error_raises(self, mock_put: MagicMock, _url: MagicMock) -> None:
        """A failed recalculation raises."""
        mock_put.return_value = fake_response(HTTPStatus.INTERNAL_SERVER_ERROR)
        with self.assertRaises(requests.HTTPError):
            database_layers.recalculate_layer_bounds("ws", "store", "layer")

    @patch("eddie.geoserver.database_layers.requests.get")
    def test_empty_bounds_warn(self, mock_get: MagicMock, _url: MagicMock) -> None:
        """Empty or missing bounds, e.g. a SQL view with no rows, are logged as a warning."""
        for bbox in ({"minx": 0, "maxx": -1, "miny": 0, "maxy": -1}, None):
            mock_get.return_value = fake_response(HTTPStatus.OK, {"featureType": {"latLonBoundingBox": bbox}})
            with self.assertLogs(database_layers.log, level="WARNING") as logs:
                database_layers._warn_if_empty_bounds("ws", "store", "layer")  # pylint: disable=protected-access
            self.assertIn("empty bounds", logs.output[0])

    @patch("eddie.geoserver.database_layers.requests.get")
    def test_real_bounds_do_not_warn(self, mock_get: MagicMock, _url: MagicMock) -> None:
        """Real bounds are not warned about."""
        bbox = {"minx": "172.4", "maxx": "172.8", "miny": "-43.6", "maxy": "-43.4"}
        mock_get.return_value = fake_response(HTTPStatus.OK, {"featureType": {"latLonBoundingBox": bbox}})
        with self.assertNoLogs(database_layers.log, level="WARNING"):
            database_layers._warn_if_empty_bounds("ws", "store", "layer")  # pylint: disable=protected-access


if __name__ == '__main__':
    unittest.main()
