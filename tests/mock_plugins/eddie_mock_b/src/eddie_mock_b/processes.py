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

"""WPS process of mock plugin B."""

import pathlib

import geopandas as gpd
import numpy as np
from pywps import LiteralInput, LiteralOutput, Process
from pywps.app.WPSRequest import WPSRequest
from pywps.response.execute import ExecuteResponse
import rasterio
from rasterio.transform import from_bounds
import shapely

from eddie import geoserver
from eddie.digitaltwin.caching.cache_common import compute_params_hash
from eddie.digitaltwin.caching.find_cached_result import find_cached_result
from eddie.digitaltwin.caching.store_cached_result import store_cached_result

WORKSPACE = "mock_b"
REGION = gpd.GeoDataFrame(geometry=[shapely.box(250000, -1350000, 350000, -1250000)], crs=3031)  # Ross Island


def _raster(request: WPSRequest, response: ExecuteResponse) -> ExecuteResponse:
    """
    Publish a 2x2 raster over the region filled with the "size" input, unless it is cached for exactly this region.

    Parameters
    ----------
    request : WPSRequest
        The WPS request, with the raster value as the "size" input.
    response : ExecuteResponse
        The WPS response to fill in.

    Returns
    -------
    ExecuteResponse
        The response, with the published layer name as the "layer" output.
    """
    process_id = response.process.identifier  # Namespaced by core: "mock_b.model"
    params = {"size": request.inputs["size"][0].data}
    aoi = REGION.to_crs(4326)
    layer = find_cached_result(process_id, params, aoi)
    if layer is None:
        layer = f"raster_{compute_params_hash(params)[:8]}"
        gtiff_path = pathlib.Path(response.process.workdir) / f"{layer}.tif"
        with rasterio.open(gtiff_path, "w", driver="GTiff", width=2, height=2, count=1, dtype="float32",
                           crs=REGION.crs, transform=from_bounds(*REGION.total_bounds, 2, 2)) as raster:
            raster.write(np.full((1, 2, 2), params["size"], dtype="float32"))
        geoserver.create_workspace_if_not_exists(WORKSPACE)
        geoserver.add_gtiff_to_geoserver(gtiff_path, WORKSPACE, layer, display_crs="EPSG:3031")
        store_cached_result(process_id, params, layer, aoi)
    response.outputs["layer"].data = layer
    return response


processes = [Process(_raster, "model", "Mock raster",
                     inputs=[LiteralInput("size", "Raster value", data_type="float")],
                     outputs=[LiteralOutput("layer", "Published layer", data_type="string")])]
