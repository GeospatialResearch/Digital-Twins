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


"""Unit tests for `eddie.app`: `/wps` stays mounted beside Flask, and still sends CORS headers."""

import importlib
import sys
import unittest
from unittest.mock import patch

ORIGIN = "https://terria.example"


def _fake_wps_service(environ: dict, start_response: callable) -> list[bytes]:
    """Stand in for the PyWPS Service: reply with the path it was given."""
    start_response("200 OK", [("Content-Type", "text/plain")])
    return [environ["PATH_INFO"].encode()]


def _client():
    """Import `eddie.app` afresh with a stand-in WPS service, and return a test client."""
    sys.modules.pop("eddie.app", None)
    with patch("eddie.wps.build_service", return_value=_fake_wps_service):
        return importlib.import_module("eddie.app").app.test_client()


class TestWpsCors(unittest.TestCase):
    """`/wps` is mounted outside Flask, so PyWPS sees its own paths, and a wrapper adds the CORS headers."""

    @classmethod
    def setUpClass(cls):
        cls.client = _client()

    def test_get_is_served_with_cors_header(self):
        response = self.client.get("/wps?service=WPS&request=GetCapabilities", headers={"Origin": ORIGIN})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), ORIGIN)

    def test_post_is_served_with_cors_header(self):
        response = self.client.post("/wps", data=b"<wps:Execute/>", headers={"Origin": ORIGIN})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), ORIGIN)

    def test_preflight_is_answered(self):
        response = self.client.options("/wps", headers={
            "Origin": ORIGIN, "Access-Control-Request-Method": "POST"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), ORIGIN)
        self.assertIn("POST", response.headers.get("Access-Control-Allow-Methods"))

    def test_subpaths_reach_pywps_without_the_prefix(self):
        response = self.client.get("/wps/processes?service=WPS", headers={"Origin": ORIGIN})
        self.assertEqual(response.data, b"/processes")
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), ORIGIN)
