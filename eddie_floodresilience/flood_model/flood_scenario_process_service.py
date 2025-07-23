# # -*- coding: utf-8 -*-
# Copyright © 2021-2025 Geospatial Research Institute Toi Hangarau
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

"""Defines PyWPS WebProcessingService process for creating a flooding scenario."""

import json
from urllib.parse import urlencode
import xml.etree.ElementTree as et

from pywps import BoundingBoxInput, ComplexOutput, Format, LiteralInput, Process, WPSRequest
from pywps.response.execute import ExecuteResponse
import requests
from shapely import box

from eddie_floodresilience import tasks
from src.config import cast_str_to_bool, EnvVariable as EnvVar


class FloodScenarioProcessService(Process):
    """Class representing a WebProcessingService process for creating a flooding scenario"""

    # pylint: disable=too-few-public-methods

    def __init__(self) -> None:
        """Define inputs and outputs of the WPS process, and assign process handler."""
        # Create bounding box WPS inputs
        inputs = [
            BoundingBoxInput("bboxIn", "Area of Interest", crss=["epsg:4326"]),
            LiteralInput("projYear", "Projected Year", data_type="integer",
                         allowed_values=list(range(2026, 2151))),
            LiteralInput("percentile", "Percentile", data_type="integer", allowed_values=[17, 50, 83], default=50),
            LiteralInput("sspScenario", "SSP Scenario", data_type="string", allowed_values=[
                "SSP1-1.9",
                "SSP1-2.6",
                "SSP2-4.5",
                "SSP3-7",
                "SSP5-8.5"
            ], default="SSP2-4.5"),
            LiteralInput("addVlm", "Add Vertical Land Movement", data_type="string", allowed_values=["True", "False"])
        ]
        # Create area WPS outputs
        outputs = [
            ComplexOutput("floodedBuildings", "Flooded Buildings",
                          supported_formats=[Format("application/vnd.terriajs.catalog-member+json")]),
            ComplexOutput("floodDepth", "Maximum Flood Depth",
                          supported_formats=[Format("application/vnd.terriajs.catalog-member+json")])
        ]

        # Initialise the process
        super().__init__(
            self._handler,
            identifier="fredt",
            title="Model a flood scenario.",
            inputs=inputs,
            outputs=outputs,
        )

    @staticmethod
    def _handler(request: WPSRequest, response: ExecuteResponse) -> None:
        """
        Process handler for modelling a flood scenario

        Parameters
        ----------
        request : WPSRequest
            The WPS request, containing input parameters.
        response : ExecuteResponse
            The WPS response, containing output data.
        """
        # Get coordinates from bounding box input
        bounding_box_input = request.inputs['bboxIn'][0]
        ymin, xmin = bounding_box_input.ll  # lower left
        ymax, xmax = bounding_box_input.ur  # upper right

        # Form bounding box into standard shapely.box
        bounding_box = box(xmin, ymin, xmax, ymax)

        scenario_options = {
            "proj_year": request.inputs["projYear"][0].data,
            "percentile": request.inputs["percentile"][0].data,
            "ssp_scenario": request.inputs["sspScenario"][0].data,
            "add_vlm": cast_str_to_bool(request.inputs["addVlm"][0].data),
            "confidence_level": "medium"
        }

        modelling_task = tasks.create_model_for_area(bounding_box.wkt, scenario_options)
        scenario_id = modelling_task.get()

        # Add Geoserver JSON Catalog entries to WPS response for use by Terria
        response.outputs['floodedBuildings'].data = json.dumps(building_flood_status_catalog(scenario_id))
        response.outputs['floodDepth'].data = json.dumps(flood_depth_catalog(scenario_id))


def building_flood_status_catalog(scenario_id: int) -> dict:
    """
    Create a dictionary in the format of a terria js catalog json for the building flood status layer.

    Parameters
    ----------
    scenario_id : int
        The ID of the scenario to create the catalog item for.

    Returns
    ----------
    dict
        The TerriaJS catalog item JSON for the building flood status layer.
    """
    dataset_name = "Building Flood Status"
    gs_building_workspace = f"{EnvVar.POSTGRES_DB}-buildings"
    gs_building_url = f"{EnvVar.GEOSERVER_HOST}:{EnvVar.GEOSERVER_PORT}/geoserver/{gs_building_workspace}/ows"
    # Open and read HTML/mustache template file for infobox
    with open("./eddie_floodresilience/flood_model/templates/flooded_building_infobox.mustache", encoding="utf-8") as file:
        flooded_building_infobox_template = file.read()
    return {
        "type": "wfs",
        "name": dataset_name,
        "url": gs_building_url,
        "typeNames": f"{gs_building_workspace}:building_flood_status",
        "parameters": {
            "viewparams": f"scenario:{scenario_id}",
        },
        "maxFeatures": 300000,
        "heightProperty": "extruded_height",
        "featureInfoTemplate": {
            "name": "Building Flood Status - {{flood_model_id}} - {{building_outline_id}}",
            "template": flooded_building_infobox_template
        },
        "legends": [{
            "title": "Building Flood Status",
            "items": [
                {
                    "title": "Non-Flooded",
                    "color": "darkgreen"
                },
                {
                    "title": "Flooded",
                    "color": "darkred"
                }
            ]
        }]
    }


def flood_depth_catalog(scenario_id: int) -> dict:
    """
    Create a dictionary in the format of a terria js catalog json for the flood depth layer.

    Parameters
    ----------
    scenario_id : int
        The ID of the scenario to create the catalog item for.

    Returns
    ----------
    dict
        The TerriaJS catalog item JSON for the flood depth layer.
    """
    gs_flood_model_workspace = f"{EnvVar.POSTGRES_DB}-dt-model-outputs"
    gs_flood_url = f"{EnvVar.GEOSERVER_HOST}:{EnvVar.GEOSERVER_PORT}/geoserver/{gs_flood_model_workspace}/wms"
    layer_name = f"{gs_flood_model_workspace}:output_{scenario_id}"
    style_name = "viridis_raster"

    # Parameters for the Geoserver GetLegendGraphic request
    legend_url_params = {
        "service": "WMS",
        "version": "1.3.0",
        "request": "GetLegendGraphic",
        "format": "image/png",
        "sld_version": "1.1.0",
        "layer": layer_name,
        "style": style_name,
        "transparent": "true",
        "LEGEND_OPTIONS": "hideEmptyRules:true;"
                          "forceLabels:on;"
                          "labelMargin:5;"
                          "fontColor:0xffffff;"
                          "fontStyle:bold;"
                          "fontAntiAliasing:true;"
    }
    legend_url = f"{gs_flood_url}?{urlencode(legend_url_params)}"

    # Retrieve times available time slices for layer
    time_dimension = query_time_dimension(gs_flood_model_workspace, layer_name)

    return {
        "type": "wms",
        "name": "Flood Depth",
        "url": gs_flood_url,
        "layers": layer_name,
        "styles": style_name,
        "supportsGetTimeseries": True,
        "multiplierDefaultDeltaStep": 6,  # Slow down timeline to give more time for rasters to load.
        "getFeatureInfoParameters": {
            "request": "GetTimeSeries",  # Terria tries to send "GetTimeseries", but Geoserver ncWMS is case-sensitive.
            "time": time_dimension  # Must manually fill time dimension because getFeatureInfoParameters overrides it.
        },
        "featureInfoTemplate": {
            "name": f"Flood depth - {scenario_id}",
        },
        "legends": [{
            "title": "Flood Depth",
            "url": legend_url,
            "urlMimeType": "image/png"
        }],
    }


def query_time_dimension(gs_flood_model_workspace: str, layer_name: str) -> str:
    """
    Query Geoserver to find the time slices available for a given layer.

    Parameters
    ----------
    gs_flood_model_workspace : str
        The name of the Geoserver workspace.
    layer_name : str
        The name of the Geoserver layer to query.

    Returns
    ----------
    str
        Comma-separated list of time slices available in ISO8601 format
        e.g. "2000-01-01T00:00:00.000Z,2000-01-01T00:00:01.000Z,2000-01-01T00:00:02.000Z"
    """
    # Get the URL for sending a request from within the docker container
    internal_workspace_wms_url = (f"{EnvVar.GEOSERVER_INTERNAL_HOST}:{EnvVar.GEOSERVER_INTERNAL_PORT}"
                                  f"/geoserver/{gs_flood_model_workspace}/wms")
    query_parameters = {
        "request": "GetCapabilities",
        "dataset": layer_name,
    }
    capabilities_response = requests.post(internal_workspace_wms_url, params=query_parameters)
    xml_root = et.fromstring(capabilities_response.content)
    namespaces = {"wms": "http://www.opengis.net/wms"}
    time_dim_elem = xml_root.find('.//wms:Dimension[@name="time"]', namespaces)

    return time_dim_elem.text
