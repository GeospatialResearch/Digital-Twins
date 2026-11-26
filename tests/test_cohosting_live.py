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

import json
import os
import unittest
from urllib.parse import urlencode
from urllib.request import urlopen
from xml.etree import ElementTree

import pytest

BASE_URL = os.environ.get("EDDIE_INGRESS_URL", "").rstrip("/")
WMS = "{http://www.opengis.net/wms}"
# (process, GeoServer workspace, Terria group, native EPSG, modelled region as lon/lat min/max)
PROCESSES = [
    ("mock_a.vector", "mock_a", "Mock A", 2193, (166, -48, 179, -34)),  # New Zealand
    ("mock_b.raster", "mock_b", "Mock B", 3031, (-180, -90, 180, -60)),  # Antarctica
]


def get(path: str, **params: str) -> tuple[bytes, str]:
    """GET a path through the ingress, returning the body and content type."""
    with urlopen(f"{BASE_URL}{path}?{urlencode(params)}", timeout=120) as response:
        return response.read(), response.headers.get_content_type()


def execute(identifier: str) -> str:
    """Run a mock process with the same parameters as the other one, returning the published layer name."""
    body, _ = get("/wps", service="WPS", version="1.0.0", request="Execute", identifier=identifier,
                  datainputs="size=250", rawdataoutput="layer")
    return body.decode()


@unittest.skipUnless(BASE_URL, "Set EDDIE_INGRESS_URL to a fresh instance running both mock plugins.")
class CoHostingLiveTest(unittest.TestCase):
    """Tests both mock plugins' processes run, publish and render on one fresh instance."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.layers = {identifier: execute(identifier) for identifier, *_ in PROCESSES}

    def test_get_capabilities_lists_both_processes_namespaced(self) -> None:
        body, _ = get("/wps", service="WPS", request="GetCapabilities")
        identifiers = {e.text for e in ElementTree.fromstring(body).iter("{http://www.opengis.net/ows/1.1}Identifier")}
        self.assertLessEqual({identifier for identifier, *_ in PROCESSES}, identifiers)

    def test_outputs_render_in_native_crs_within_modelled_region(self) -> None:
        for identifier, workspace, _, epsg, region in PROCESSES:
            with self.subTest(identifier):
                body, _ = get(f"/geoserver/{workspace}/wms", service="WMS", version="1.3.0", request="GetCapabilities")
                layer = next(e for e in ElementTree.fromstring(body).iter(f"{WMS}Layer")
                             if e.findtext(f"{WMS}Name") in (self.layers[identifier],
                                                             f"{workspace}:{self.layers[identifier]}"))
                geographic = layer.find(f"{WMS}EX_GeographicBoundingBox")
                west, south, east, north = (float(geographic.findtext(f"{WMS}{side}")) for side in
                                            ("westBoundLongitude", "southBoundLatitude",
                                             "eastBoundLongitude", "northBoundLatitude"))
                self.assertTrue(region[0] <= west <= east <= region[2] and region[1] <= south <= north <= region[3],
                                (west, south, east, north))
                native = next(e for e in layer.iter(f"{WMS}BoundingBox") if e.get("CRS") == f"EPSG:{epsg}")
                bbox = ",".join(native.get(side) for side in ("minx", "miny", "maxx", "maxy"))
                image, content_type = get(f"/geoserver/{workspace}/wms", service="WMS", version="1.3.0",
                                          request="GetMap", layers=self.layers[identifier], styles="",
                                          crs=f"EPSG:{epsg}", bbox=bbox, width="64", height="64",
                                          format="image/png")
                self.assertEqual("image/png", content_type, image[:300])

    def test_terria_catalog_serves_both_outputs_from_the_same_origin(self) -> None:
        body, _ = get("/terria-catalog.json")
        groups = {group["name"]: group["members"] for group in json.loads(body)["catalog"]}
        for identifier, _, group, *_ in PROCESSES:
            with self.subTest(identifier):
                member = next(m for m in groups[group] if m["name"] == self.layers[identifier])
                self.assertTrue(member["url"].startswith(f"{BASE_URL}/geoserver/"), member["url"])

    def test_identical_parameters_give_each_plugin_its_own_layer(self) -> None:
        self.assertEqual(len(PROCESSES), len(set(self.layers.values())), self.layers)

    @pytest.mark.xfail(strict=True, reason="BUG: find_cached_result reads row.id but only selects output_id")
    def test_rerun_is_a_cache_hit_for_its_own_plugin(self) -> None:
        self.assertEqual(self.layers, {identifier: execute(identifier) for identifier in self.layers})


if __name__ == "__main__":
    unittest.main()
