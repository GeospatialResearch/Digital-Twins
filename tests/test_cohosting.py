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
Tests for co-hosting two plugins in one EDDIE instance, through the real eddie.app.
eddie_mock_a (vector, EPSG:2193, spatial cache reuse) and eddie_mock_b (raster, EPSG:3031, no reuse) live in
tests/mock_plugins. GeoServer, PostGIS and the cache table are faked; test_cohosting_live.py covers the real stack.
"""

import contextlib
import importlib
import pathlib
import pkgutil
import sys
import tempfile
import tomllib
import unittest
from http import HTTPStatus
from importlib.metadata import EntryPoint
from unittest import mock
from xml.etree import ElementTree

import celery
import geopandas as gpd
from pywps import configuration
import rasterio
import shapely

import eddie
from eddie.config import EnvVariable
from eddie.digitaltwin import setup_environment
from eddie.digitaltwin.caching import cache_common
from eddie import discover_plugins
from eddie.discover_plugins import ENTRY_POINT_GROUP
from tests.test_geoserver.test_database_layers import fake_response

MOCK_PLUGINS = pathlib.Path(__file__).parent / "mock_plugins"
PLUGINS = ("eddie_mock_a", "eddie_mock_b")
WPS_NS = {"wps": "http://www.opengis.net/wps/1.0.0", "ows": "http://www.opengis.net/ows/1.1"}
# Independent of the plugins' own constants, so a plugin that models the wrong place fails
NZ = shapely.box(166, -48, 179, -34)
SOUTH_OF_60 = shapely.box(-180, -90, 180, -60)


def declared_entry_points() -> list[EntryPoint]:
    """The "eddie.plugins" entry points each mock plugin's pyproject.toml declares, as pip would install them."""
    entry_points = []
    for plugin in PLUGINS:
        project = tomllib.loads((MOCK_PLUGINS / plugin / "pyproject.toml").read_text())["project"]
        declared = project["entry-points"][ENTRY_POINT_GROUP]
        entry_points += [EntryPoint(name, module, ENTRY_POINT_GROUP) for name, module in declared.items()]
    return entry_points


class CoHostingTest(unittest.TestCase):
    """
    Tests for both mock plugins installed together in the real eddie.app.

    eddie.tasks discovers plugins and eddie.app builds the WPS service at import time, and build_processes renames
    each plugin's Process instances in place. So the class imports eddie.tasks, eddie.app and both plugins afresh,
    and puts back whatever was imported before afterwards; otherwise test order would change the results.
    """

    @classmethod
    def setUpClass(cls) -> None:
        stack = contextlib.ExitStack()
        cls.addClassCleanup(stack.close)
        fresh = ("eddie.tasks", "eddie.app", *PLUGINS,
                 *(f"{plugin}.{module}" for plugin in PLUGINS for module in ("blueprint", "catalog", "processes")))
        saved_modules = {name: sys.modules.pop(name, None) for name in fresh}
        saved_attrs = {name: vars(eddie).pop(name, None) for name in ("tasks", "app")}

        def restore() -> None:
            for name, module in saved_modules.items():
                sys.modules.pop(name, None)
                if module is not None:
                    sys.modules[name] = module
            for name, module in saved_attrs.items():
                vars(eddie).pop(name, None)
                if module is not None:
                    vars(eddie)[name] = module

        stack.callback(restore)
        # Importing eddie.tasks again makes its new Celery app current, and PyWPS reloads its global config
        stack.callback(celery.current_app._get_current_object().set_current)  # pylint: disable=protected-access
        stack.enter_context(mock.patch.object(configuration, "CONFIG", configuration.CONFIG))
        # PyWPS writes logs and outputs relative to the working directory; from src/ it would load src/pywps.cfg
        stack.enter_context(contextlib.chdir(stack.enter_context(tempfile.TemporaryDirectory())))
        src_dirs = [str(MOCK_PLUGINS / plugin / "src") for plugin in PLUGINS]
        stack.enter_context(mock.patch.object(sys, "path", sys.path + src_dirs))
        stack.enter_context(mock.patch.object(discover_plugins, "entry_points", return_value=declared_entry_points()))
        # Only scan the mock plugins for 'eddie_' packages, so a plugin installed in this environment is not loaded
        stack.enter_context(mock.patch.object(discover_plugins.pkgutil, "iter_modules",
                                              return_value=list(pkgutil.iter_modules(src_dirs))))
        stack.enter_context(mock.patch.object(cache_common, "_spatial_containment_opt_in", set()))
        cls.discovery_warning = stack.enter_context(mock.patch.object(discover_plugins.log, "warning"))

        cls.app = importlib.import_module("eddie.app").app
        cls.mock_a, cls.mock_b = (sys.modules[f"{plugin}.processes"] for plugin in PLUGINS)
        cls.client = cls.app.test_client()

    def execute(self, identifier: str, size: float, cache: dict) -> tuple[str, mock.MagicMock, list]:
        """
        Execute a WPS process through /wps with GeoServer, PostGIS and the cache table faked.

        Returns the published layer name, the GeoServer mock, and what was written: the frame sent to PostGIS for
        mock_a, or (epsg, bounds) of the GeoTIFF sent to GeoServer for mock_b.
        """
        def find(process_id: str, params: dict, *_args: object) -> str | None:
            return cache.get((process_id, cache_common.compute_params_hash(params)))

        def store(process_id: str, params: dict, output_id: str, *_args: object) -> str:
            cache[(process_id, cache_common.compute_params_hash(params))] = output_id
            return output_id

        written = []

        def read_gtiff(path: pathlib.Path, *_args: object, **_kwargs: object) -> None:
            with rasterio.open(path) as raster:  # Read now, PyWPS deletes its workdir after the request
                written.append((raster.crs.to_epsg(), raster.bounds))

        plugin = self.mock_a if identifier.startswith("mock_a.") else self.mock_b
        with mock.patch.object(plugin, "find_cached_result", side_effect=find), \
                mock.patch.object(plugin, "store_cached_result", side_effect=store), \
                mock.patch.object(plugin, "geoserver", autospec=True) as geoserver, \
                mock.patch.object(setup_environment, "get_database"), \
                mock.patch.object(gpd.GeoDataFrame, "to_postgis", autospec=True) as to_postgis:
            geoserver.add_gtiff_to_geoserver.side_effect = read_gtiff
            response = self.client.get(f"/wps?service=WPS&version=1.0.0&request=Execute&identifier={identifier}"
                                       f"&datainputs=size={size}&rawdataoutput=layer")
        self.assertEqual(HTTPStatus.OK, response.status_code, response.text)
        written += [call.args[0] for call in to_postgis.call_args_list]
        return response.text, geoserver, written

    def test_plugins_found_by_their_declared_entry_points(self) -> None:
        # Finding them only by the deprecated 'eddie_' prefix logs a warning
        self.assertEqual(PLUGINS, tuple(sys.modules["eddie.tasks"].eddie_plugins))
        self.discovery_warning.assert_not_called()

    def test_get_capabilities_lists_both_processes_namespaced(self) -> None:
        response = self.client.get("/wps?service=WPS&request=GetCapabilities")
        self.assertEqual(HTTPStatus.OK, response.status_code)
        identifiers = {element.text for element in
                       ElementTree.fromstring(response.data).iterfind(".//wps:Process/ows:Identifier", WPS_NS)}
        self.assertEqual({"mock_a.model", "mock_b.model"}, identifiers)

    def test_vector_process_publishes_nztm_layer_in_region(self) -> None:
        layer, geoserver, (frame,) = self.execute("mock_a.model", 250, {})
        self.assertEqual(2193, frame.crs.to_epsg())
        self.assertTrue(NZ.contains(shapely.box(*frame.to_crs(4326).total_bounds)))
        geoserver.create_datastore_layer.assert_called_once_with(
            "mock_a", geoserver.create_main_db_store.return_value, layer)

    def test_raster_process_publishes_polar_layer_in_region(self) -> None:
        layer, geoserver, ((epsg, bounds),) = self.execute("mock_b.model", 250, {})
        self.assertEqual(3031, epsg)
        region = gpd.GeoSeries([shapely.box(*bounds)], crs=epsg).to_crs(4326)
        self.assertTrue(SOUTH_OF_60.contains(shapely.box(*region.total_bounds)))
        geoserver.create_workspace_if_not_exists.assert_called_once_with("mock_b")
        path = geoserver.add_gtiff_to_geoserver.call_args.args[0]
        self.assertEqual(f"{layer}.tif", path.name)
        geoserver.add_gtiff_to_geoserver.assert_called_once_with(path, "mock_b", layer, display_crs="EPSG:3031")

    def test_identical_parameters_do_not_collide_in_cache(self) -> None:
        cache = {}
        layer_a, _, _ = self.execute("mock_a.model", 250, cache)
        layer_b, _, _ = self.execute("mock_b.model", 250, cache)
        # Both plugins name their process "model", so only core's namespacing keeps these keys apart
        self.assertEqual({"mock_a.model", "mock_b.model"}, {process_id for process_id, _ in cache})
        # Second runs are cache hits, each returning its own plugin's layer without publishing again
        for identifier, layer in (("mock_a.model", layer_a), ("mock_b.model", layer_b)):
            with self.subTest(identifier):
                hit, geoserver, written = self.execute(identifier, 250, cache)
                self.assertEqual(layer, hit)
                self.assertEqual([], written)
                self.assertEqual([], geoserver.mock_calls)

    def test_only_mock_a_opts_in_to_spatial_reuse(self) -> None:
        self.assertTrue(cache_common.supports_spatial_containment("mock_a.model"))
        self.assertFalse(cache_common.supports_spatial_containment("mock_b.model"))

    def test_each_plugin_serves_its_own_route(self) -> None:
        # A blueprint name collision would already raise in setUpClass; a shadowed route answers with the other body
        for path, body in (("/mock-a", "mock_a"), ("/mock-b", "mock_b")):
            with self.subTest(path):
                self.assertEqual(body, self.client.get(path).text)

    @mock.patch.object(EnvVariable, "EDDIE_AUTOSERVE_CATALOG", False)
    @mock.patch("requests.get", return_value=fake_response(HTTPStatus.NOT_FOUND))
    def test_terria_catalog_contains_both_plugins(self, *_mocks: mock.MagicMock) -> None:
        catalog = self.client.get("/terria-catalog.json").get_json()["catalog"]
        self.assertEqual(["Mock A", "Mock B"], [group["name"] for group in catalog])


if __name__ == "__main__":
    unittest.main()
