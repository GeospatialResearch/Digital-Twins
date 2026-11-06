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
import xml.etree.ElementTree as ET
from http import HTTPStatus
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import rasterio as rio
import requests
from rasterio.coords import BoundingBox
from rasterio.transform import from_bounds

from eddie.config import EnvVariable
from eddie.geoserver import raster_layers
from tests.test_geoserver.test_database_layers import fake_response

MODULE = "eddie.geoserver.raster_layers"


def _write_gtiff(
        path: pathlib.Path,
        crs: str | None,
        bounds: tuple[float, float, float, float],
        count: int = 1,
        dtype: str = "float32",
        descriptions: tuple[str, ...] | None = None,
        units: tuple[str | None, ...] | None = None
) -> pathlib.Path:
    """
    Write a small 4x4 GeoTiff for tests.

    Parameters
    ----------
    path : pathlib.Path
        Where to write the file.
    crs : str | None
        The CRS of the file, e.g. "EPSG:2193". None writes a file with no CRS.
    bounds : tuple[float, float, float, float]
        The bounds of the file: minx, miny, maxx, maxy in units of crs.
    count : int = 1
        The number of bands.
    dtype : str = "float32"
        The data type of the bands.
    descriptions : tuple[str, ...] | None = None
        The band descriptions, one per band.
    units : tuple[str | None, ...] | None = None
        The band units, one per band.

    Returns
    -------
    pathlib.Path
        The path of the written file.
    """
    with rio.open(path, "w", driver="GTiff", width=4, height=4, count=count, dtype=dtype, crs=crs,
                  transform=from_bounds(*bounds, 4, 4)) as dst:
        for band in range(1, count + 1):
            dst.write(np.ones((4, 4), dtype=dtype), band)
        if descriptions:
            dst.descriptions = descriptions
        if units:
            dst.units = units
    return path


class _TmpDirTestCase(unittest.TestCase):
    """Provides a temporary directory, self.tmp_dir, that is removed after each test."""

    def setUp(self) -> None:
        """Create the temporary directory."""
        tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(tmp_dir.cleanup)
        self.tmp_dir = pathlib.Path(tmp_dir.name)


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


class GtiffNativeCrsTest(_TmpDirTestCase):
    """Tests get_gtiff_native_crs."""

    def test_reads_crs_from_file(self) -> None:
        """The CRS is read from the file as an EPSG string."""
        gtiff = _write_gtiff(self.tmp_dir / "a.tif", "EPSG:2193", (1570000, 5180000, 1580000, 5190000))
        self.assertEqual("EPSG:2193", raster_layers.get_gtiff_native_crs(gtiff))

    def test_missing_crs_raises(self) -> None:
        """A file with no CRS fails loudly."""
        gtiff = _write_gtiff(self.tmp_dir / "a.tif", None, (0, 0, 10, 10))
        with self.assertRaises(ValueError):
            raster_layers.get_gtiff_native_crs(gtiff)

    def test_reads_utm_and_polar_crs(self) -> None:
        """East/north projected CRSs are read with their own EPSG code, not a default."""
        for epsg, bounds in ((32759, (600000, 5170000, 610000, 5180000)),
                             (3031, (-500000, -500000, 500000, 500000))):
            gtiff = _write_gtiff(self.tmp_dir / f"{epsg}.tif", f"EPSG:{epsg}", bounds)
            with self.subTest(epsg=epsg):
                self.assertEqual(f"EPSG:{epsg}", raster_layers.get_gtiff_native_crs(gtiff))

    def test_crs_without_epsg_raises(self) -> None:
        """A custom CRS with no EPSG code is refused, naming the file, rather than returned as 'EPSG:None'."""
        gtiff = _write_gtiff(self.tmp_dir / "custom.tif", "+proj=tmerc +lon_0=101.3 +ellps=GRS80", (0, 0, 10, 10))
        with self.assertRaisesRegex(ValueError, "custom.tif"):
            raster_layers.get_gtiff_native_crs(gtiff)


class CheckDisplayCrsTest(_TmpDirTestCase):
    """Tests check_display_crs."""

    def _gtiff(self, bounds: tuple[float, float, float, float], crs: str = "EPSG:4326") -> pathlib.Path:
        """Write a GeoTiff with the given bounds."""
        return _write_gtiff(self.tmp_dir / "a.tif", crs, bounds)

    def test_none_skips_checks(self) -> None:
        """No display CRS means no restrictions, even at the poles."""
        raster_layers.check_display_crs(self._gtiff((0, 80, 10, 89)), None)

    def test_3857_refused_beyond_max_lat(self) -> None:
        """Web mercator is refused for rasters beyond its maximum latitude."""
        gtiff = self._gtiff((0, 80, 10, 86))
        with self.assertRaises(ValueError):
            raster_layers.check_display_crs(gtiff, "EPSG:3857")

    def test_3857_allowed_within_max_lat(self) -> None:
        """Web mercator is allowed for rasters within its maximum latitude."""
        raster_layers.check_display_crs(self._gtiff((0, 80, 10, 85)), "EPSG:3857")

    def test_3857_refused_polar_stereographic_enclosing_pole(self) -> None:
        """A polar raster whose corners are all inside the limit is still refused, as its edges reach the pole."""
        for crs in ("EPSG:3031", "EPSG:3413"):
            gtiff = self._gtiff((-500000, -500000, 500000, 500000), crs)
            with self.subTest(crs=crs), self.assertRaisesRegex(ValueError, "EPSG:3857"):
                raster_layers.check_display_crs(gtiff, "EPSG:3857")

    def test_other_display_crs_allowed(self) -> None:
        """Display CRSs other than web mercator are allowed, without the web mercator latitude limit."""
        raster_layers.check_display_crs(self._gtiff((0, 80, 10, 89)), "EPSG:4326")

    def test_display_crs_without_epsg_refused(self) -> None:
        """A display CRS with no EPSG code is refused."""
        gtiff = self._gtiff((0, 80, 10, 85))
        with self.assertRaises(ValueError):
            raster_layers.check_display_crs(gtiff, "+proj=merc +lon_0=100 +datum=WGS84")

    def test_3857_refused_beyond_southern_max_lat(self) -> None:
        """Web mercator is refused for rasters beyond its maximum latitude in the southern hemisphere."""
        gtiff = self._gtiff((0, -86, 10, -80))
        with self.assertRaisesRegex(ValueError, "a.tif"):
            raster_layers.check_display_crs(gtiff, "EPSG:3857")

    def test_3857_alias_is_guarded(self) -> None:
        """Web mercator spelled differently is still guarded, since the check compares EPSG codes."""
        gtiff = self._gtiff((0, 80, 10, 86))
        with self.assertRaises(ValueError):
            raster_layers.check_display_crs(gtiff, "epsg:3857")

    def test_polar_raster_allowed_in_3031(self) -> None:
        """A raster enclosing the pole may be displayed in a polar CRS."""
        gtiff = self._gtiff((-500000, -500000, 500000, 500000), "EPSG:3031")
        raster_layers.check_display_crs(gtiff, "EPSG:3031")


class ReprojectRasterTest(_TmpDirTestCase):
    """Tests reproject_raster."""

    def test_output_in_dst_crs(self) -> None:
        """The reprojected copy is in the requested CRS."""
        src = _write_gtiff(self.tmp_dir / "src.tif", "EPSG:2193", (1570000, 5180000, 1580000, 5190000))
        for epsg in (3857, 4326):
            dst = self.tmp_dir / f"{epsg}.tif"
            raster_layers.reproject_raster(src, dst, f"EPSG:{epsg}")
            with self.subTest(epsg=epsg), rio.open(dst) as reprojected:
                self.assertEqual(epsg, reprojected.crs.to_epsg())


class ReadCoverageDimensionsTest(_TmpDirTestCase):
    """Tests read_coverage_dimensions."""

    def test_uses_descriptions_and_units(self) -> None:
        """Band descriptions, units and data types are used."""
        gtiff = _write_gtiff(self.tmp_dir / "a.tif", "EPSG:4326", (0, 0, 1, 1), count=2, dtype="uint8",
                             descriptions=("red", "nir"), units=("m", None))
        self.assertEqual(
            [raster_layers.CoverageDimension("red", "m", "UNSIGNED_8BITS"),
             raster_layers.CoverageDimension("nir", "", "UNSIGNED_8BITS")],
            raster_layers.read_coverage_dimensions(gtiff, "lyr"))

    def test_falls_back_to_layer_name(self) -> None:
        """Bands without descriptions are named after the layer."""
        single = _write_gtiff(self.tmp_dir / "a.tif", "EPSG:4326", (0, 0, 1, 1))
        self.assertEqual([raster_layers.CoverageDimension("lyr", "", "REAL_32BITS")],
                         raster_layers.read_coverage_dimensions(single, "lyr"))
        double = _write_gtiff(self.tmp_dir / "b.tif", "EPSG:4326", (0, 0, 1, 1), count=2)
        self.assertEqual(["lyr_1", "lyr_2"],
                         [dim.band_name for dim in raster_layers.read_coverage_dimensions(double, "lyr")])

    def test_dtype_mapping(self) -> None:
        """Each band data type maps to GeoServer's dimensionType name."""
        for dtype, expected in (("int16", "SIGNED_16BITS"), ("float64", "REAL_64BITS")):
            gtiff = _write_gtiff(self.tmp_dir / f"{dtype}.tif", "EPSG:4326", (0, 0, 1, 1), dtype=dtype)
            with self.subTest(dtype=dtype):
                self.assertEqual([raster_layers.CoverageDimension("lyr", "", expected)],
                                 raster_layers.read_coverage_dimensions(gtiff, "lyr"))


class FormatCoverageDimensionsTest(unittest.TestCase):
    """Tests format_coverage_dimensions."""

    @staticmethod
    def _parse(coverage_dimensions: list) -> list[tuple[str, str, str]]:
        """Format the dimensions and parse them back to (name, unit, dimensionType name) per element."""
        root = ET.fromstring(f"<r>{raster_layers.format_coverage_dimensions(coverage_dimensions)}</r>")
        return [(dim.findtext("name"), dim.findtext("unit"), dim.findtext("dimensionType/name"))
                for dim in root.findall("coverageDimension")]

    def test_empty_raises(self) -> None:
        """An empty list is refused rather than producing a coverage with no bands."""
        with self.assertRaises(ValueError):
            raster_layers.format_coverage_dimensions([])

    def test_one_element_per_dimension_in_order(self) -> None:
        """Each dimension becomes one coverageDimension element, in band order."""
        dims = [raster_layers.CoverageDimension("depth", "m", "REAL_32BITS"),
                raster_layers.CoverageDimension("velocity", "m/s", "SIGNED_16BITS")]
        self.assertEqual([("depth", "m", "REAL_32BITS"), ("velocity", "m/s", "SIGNED_16BITS")], self._parse(dims))

    @pytest.mark.xfail(raises=ET.ParseError, strict=True,
                       reason="BUG: band names and units are not XML-escaped, so a band description containing '&' "
                              "makes the GeoServer payload malformed. Remove when fixed.")
    def test_escapes_xml_special_characters(self) -> None:
        """Band names from file descriptions may contain XML special characters, which must be escaped."""
        dims = [raster_layers.CoverageDimension("rain & hail", "<mm>", "REAL_32BITS")]
        self.assertEqual([("rain & hail", "<mm>", "REAL_32BITS")], self._parse(dims))


@patch(f"{MODULE}.get_workspace_raster_layers", return_value=[])
@patch(f"{MODULE}.get_geoserver_url", return_value="http://geoserver")
@patch(f"{MODULE}.requests")
class AddGtiffToGeoserverTest(_TmpDirTestCase):
    """Tests add_gtiff_to_geoserver."""

    def setUp(self) -> None:
        """Create the source file and a GeoServer data directory to copy it into."""
        super().setUp()
        (self.tmp_dir / "data" / "ws").mkdir(parents=True)
        for name, value in (("DATA_DIR_GEOSERVER", self.tmp_dir), ("DISPLAY_CRS", None)):
            patcher = patch.object(EnvVariable, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _publish(self, requests_mock: MagicMock, crs: str | None = "EPSG:4326", **kwargs: str) -> tuple:
        """Publish a 'depth' raster, returning the result and the posted coverage request."""
        requests_mock.post.return_value = fake_response(HTTPStatus.CREATED)
        source = _write_gtiff(self.tmp_dir / "lyr.tif", crs, (170, -45, 175, -40), descriptions=("depth",))
        published = raster_layers.add_gtiff_to_geoserver(source, "ws", "lyr", **kwargs)
        return published, requests_mock.post.call_args_list[-1]

    def test_returns_native_published_raster(self, requests_mock: MagicMock, _url: MagicMock, _layers: MagicMock
                                             ) -> None:
        """The native CRS and bounds are returned, and the coverage is created with recalculated bounds."""
        published, coverage_post = self._publish(requests_mock)
        expected = raster_layers.PublishedRaster("lyr", "EPSG:4326", BoundingBox(170.0, -45.0, 175.0, -40.0))
        self.assertEqual(expected, published)
        self.assertIsInstance(published.bbox, BoundingBox)
        self.assertEqual("nativebbox,latlonbbox", coverage_post.kwargs["params"]["recalculate"])
        self.assertIn("<srs>EPSG:4326</srs>", coverage_post.kwargs["data"])
        self.assertIn("<name>depth</name>", coverage_post.kwargs["data"])

    def test_reprojected_keeps_band_names(self, requests_mock: MagicMock, _url: MagicMock, _layers: MagicMock
                                          ) -> None:
        """A reprojected copy is published in the display CRS, but keeps the source's band names."""
        published, coverage_post = self._publish(requests_mock, display_crs="EPSG:3857")
        with rio.open(self.tmp_dir / "data" / "ws" / "lyr.tif") as served:
            self.assertEqual(raster_layers.PublishedRaster("lyr", "EPSG:3857", served.bounds), published)
        self.assertIn("<name>depth</name>", coverage_post.kwargs["data"])

    def test_reprojected_to_non_web_mercator(self, requests_mock: MagicMock, _url: MagicMock, _layers: MagicMock
                                             ) -> None:
        """A display CRS other than web mercator is used for the served copy and the coverage."""
        published, coverage_post = self._publish(requests_mock, display_crs="EPSG:2193")
        with rio.open(self.tmp_dir / "data" / "ws" / "lyr.tif") as served:
            self.assertEqual(2193, served.crs.to_epsg())
        self.assertEqual("EPSG:2193", published.crs)
        self.assertIn("<srs>EPSG:2193</srs>", coverage_post.kwargs["data"])

    def test_missing_crs_fails_before_geoserver(self, requests_mock: MagicMock, _url: MagicMock, layers: MagicMock
                                                ) -> None:
        """A file with no CRS is rejected before anything is changed in GeoServer."""
        with self.assertRaises(ValueError):
            self._publish(requests_mock, crs=None)
        requests_mock.post.assert_not_called()
        layers.assert_not_called()

    @patch(f"{MODULE}.delete_store")
    def test_guard_failure_keeps_existing_layer(
            self, delete_mock: MagicMock, requests_mock: MagicMock, _url: MagicMock, layers: MagicMock
    ) -> None:
        """A raster refused by the display CRS guard leaves the existing layer in place."""
        layers.return_value = ["lyr"]
        source = _write_gtiff(self.tmp_dir / "lyr.tif", "EPSG:3031", (-500000, -500000, 500000, 500000))
        with self.assertRaises(ValueError):
            raster_layers.add_gtiff_to_geoserver(source, "ws", "lyr", display_crs="EPSG:3857")
        delete_mock.assert_not_called()
        requests_mock.post.assert_not_called()

    def test_explicit_dimensions_used(self, requests_mock: MagicMock, _url: MagicMock, _layers: MagicMock) -> None:
        """Coverage dimensions passed in are used instead of those read from the file."""
        dims = [raster_layers.CoverageDimension("flood_depth", "mm", "REAL_64BITS")]
        _, coverage_post = self._publish(requests_mock, coverage_dimensions=dims)
        payload = coverage_post.kwargs["data"]
        self.assertIn("<name>flood_depth</name>", payload)
        self.assertIn("<unit>mm</unit>", payload)
        self.assertIn("<name>REAL_64BITS</name>", payload)
        self.assertNotIn("<name>depth</name>", payload)

    def test_display_crs_from_env(self, requests_mock: MagicMock, _url: MagicMock, _layers: MagicMock) -> None:
        """With no display_crs argument, EnvVariable.DISPLAY_CRS decides the served CRS."""
        with patch.object(EnvVariable, "DISPLAY_CRS", "EPSG:3857"):
            published, coverage_post = self._publish(requests_mock)
        with rio.open(self.tmp_dir / "data" / "ws" / "lyr.tif") as served:
            self.assertEqual(3857, served.crs.to_epsg())
        self.assertEqual("EPSG:3857", published.crs)
        self.assertIn("<srs>EPSG:3857</srs>", coverage_post.kwargs["data"])


if __name__ == '__main__':
    unittest.main()
