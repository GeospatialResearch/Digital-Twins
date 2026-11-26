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

"""Mock EDDIE plugin A: one vector process in EPSG:2193 whose cached results are reused for contained areas."""

import geopandas as gpd
from flask import Blueprint
from pywps import LiteralInput, LiteralOutput, Process
from pywps.app.WPSRequest import WPSRequest
from pywps.response.execute import ExecuteResponse
import shapely

from eddie import geoserver
from eddie.digitaltwin import setup_environment
from eddie.digitaltwin.caching.cache_common import compute_params_hash
from eddie.digitaltwin.caching.find_cached_result import find_cached_result
from eddie.digitaltwin.caching.store_cached_result import store_cached_result
from eddie.geoserver.terria_catalogs import CatalogGroup, get_layers_as_terria_group

WORKSPACE = "mock_a"
REGION = gpd.GeoDataFrame(geometry=[shapely.box(1565000, 5175000, 1575000, 5185000)], crs=2193)  # Christchurch

blueprint = Blueprint("eddie_mock_a", __name__)


@blueprint.route("/mock-a")
def ping() -> str:
    """
    Name this plugin, to show its route is served without colliding with other plugins.

    Returns
    -------
    str
        The plugin's workspace name.
    """
    return WORKSPACE


def catalog() -> list[CatalogGroup]:
    """
    Return the TerriaJS catalog group for the layers this plugin published.

    Returns
    -------
    list[CatalogGroup]
        One group of the layers in this plugin's GeoServer workspace.
    """
    return [get_layers_as_terria_group(WORKSPACE)]


def _vector(request: WPSRequest, response: ExecuteResponse) -> ExecuteResponse:
    """
    Publish a buffer around the region's centre, unless a cached result already covers the region.

    Parameters
    ----------
    request : WPSRequest
        The WPS request, with the buffer distance in metres as the "size" input.
    response : ExecuteResponse
        The WPS response to fill in.

    Returns
    -------
    ExecuteResponse
        The response, with the published layer name as the "layer" output.
    """
    process_id = response.process.identifier  # Namespaced by core: "mock_a.model"
    params = {"size": request.inputs["size"][0].data}
    aoi = REGION.to_crs(4326)
    layer = find_cached_result(process_id, params, aoi)
    if layer is None:
        layer = f"vector_{compute_params_hash(params)[:8]}"
        result = gpd.GeoDataFrame(geometry=REGION.centroid.buffer(params["size"]))
        result.to_postgis(layer, setup_environment.get_database(), if_exists="replace")
        geoserver.create_datastore_layer(WORKSPACE, geoserver.create_main_db_store(WORKSPACE), layer)
        store_cached_result(process_id, params, layer, aoi)
    response.outputs["layer"].data = layer
    return response


processes = [Process(_vector, "model", "Mock vector",
                     inputs=[LiteralInput("size", "Buffer distance (m)", data_type="float")],
                     outputs=[LiteralOutput("layer", "Published layer", data_type="string")])]
processes[0].supports_spatial_containment = True
