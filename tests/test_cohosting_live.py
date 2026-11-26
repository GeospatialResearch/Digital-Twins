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
Live co-hosting test against a freshly started instance with eddie_mock_a and eddie_mock_b installed.
Every request goes through the single origin in EDDIE_INGRESS_URL, which must route /wps and /terria-catalog.json to
the backend and /geoserver to GeoServer. Skipped unless EDDIE_INGRESS_URL is set.
"""

import functools
import json
import os
import unittest
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import urlopen
from xml.etree import ElementTree

BASE_URL = os.environ.get("EDDIE_INGRESS_URL", "").rstrip("/")
WMS = "{http://www.opengis.net/wms}"
# (process, GeoServer workspace, Terria group, native EPSG, modelled region as lon/lat min/max)
PROCESSES = [
    ("mock_a.model", "mock_a", "Mock A", 2193, (166, -48, 179, -34)),  # New Zealand
    ("mock_b.model", "mock_b", "Mock B", 3031, (-180, -90, 180, -60)),  # Antarctica
]


def get(path: str, **params: str) -> tuple[bytes, str]:
    """GET a path through the ingress, returning the body and content type."""
    try:
        with urlopen(f"{BASE_URL}{path}?{urlencode(params)}", timeout=120) as response:
            return response.read(), response.headers.get_content_type()
    except HTTPError as e:  # Keep the service's error report, e.g. a WPS ExceptionReport
        raise AssertionError(f"{e}: {e.read()[:500]!r}") from e


def origin(url: str) -> tuple[str, str, int]:
    """The scheme, host and port of a URL, with the scheme's default port filled in."""
    parts = urlsplit(url)
    return parts.scheme, parts.hostname, parts.port or {"http": 80, "https": 443}[parts.scheme]


@functools.cache
def execute(identifier: str) -> str:
    """Run a mock process with the same parameters as the other one, returning the published layer name."""
    body, _ = get("/wps", service="WPS", version="1.0.0", request="Execute", identifier=identifier,
                  datainputs="size=250", rawdataoutput="layer")
    return body.decode()


@unittest.skipUnless(BASE_URL, "Set EDDIE_INGRESS_URL to a fresh instance running both mock plugins.")
class CoHostingLiveTest(unittest.TestCase):
    """Tests both mock plugins' processes run, publish and render on one fresh instance."""

    def test_get_capabilities_lists_both_processes_namespaced(self) -> None:
        body, _ = get("/wps", service="WPS", request="GetCapabilities")
        identifiers = {e.text for e in ElementTree.fromstring(body).iter("{http://www.opengis.net/ows/1.1}Identifier")}
        self.assertLessEqual({identifier for identifier, *_ in PROCESSES}, identifiers)

    def test_outputs_render_in_native_crs_within_modelled_region(self) -> None:
        for identifier, workspace, _, epsg, region in PROCESSES:
            with self.subTest(identifier):
                name = execute(identifier)
                body, _ = get(f"/geoserver/{workspace}/wms", service="WMS", version="1.3.0", request="GetCapabilities")
                layer = next((e for e in ElementTree.fromstring(body).iter(f"{WMS}Layer")
                              if e.findtext(f"{WMS}Name") in (name, f"{workspace}:{name}")), None)
                self.assertIsNotNone(layer, body[:500])
                geographic = layer.find(f"{WMS}EX_GeographicBoundingBox")
                west, south, east, north = (float(geographic.findtext(f"{WMS}{side}")) for side in
                                            ("westBoundLongitude", "southBoundLatitude",
                                             "eastBoundLongitude", "northBoundLatitude"))
                self.assertTrue(region[0] <= west <= east <= region[2] and region[1] <= south <= north <= region[3],
                                (west, south, east, north))
                native = next((e for e in layer.iter(f"{WMS}BoundingBox") if e.get("CRS") == f"EPSG:{epsg}"), None)
                self.assertIsNotNone(native, f"No EPSG:{epsg} BoundingBox")
                bbox = ",".join(native.get(side) for side in ("minx", "miny", "maxx", "maxy"))
                image, content_type = get(f"/geoserver/{workspace}/wms", service="WMS", version="1.3.0",
                                          request="GetMap", layers=name, styles="",
                                          crs=f"EPSG:{epsg}", bbox=bbox, width="64", height="64",
                                          format="image/png")
                self.assertEqual("image/png", content_type, image[:300])

    def test_terria_catalog_serves_both_outputs_from_the_same_origin(self) -> None:
        body, _ = get("/terria-catalog.json")
        groups = {group["name"]: group["members"] for group in json.loads(body)["catalog"]}
        for identifier, _, group, *_ in PROCESSES:
            with self.subTest(identifier):
                member = next((m for m in groups[group] if m["name"] == execute(identifier)), None)
                self.assertIsNotNone(member, groups[group])
                self.assertEqual(origin(BASE_URL), origin(member["url"]))
                self.assertTrue(urlsplit(member["url"]).path.startswith(f"{urlsplit(BASE_URL).path}/geoserver/"))


if __name__ == "__main__":
    unittest.main()
