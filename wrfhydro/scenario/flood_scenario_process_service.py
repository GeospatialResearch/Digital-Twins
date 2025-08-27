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

"""Defines PyWPS WebProcessingService process for creating a WRF-Hydro flooding scenario."""

import json

from pywps import BoundingBoxInput, ComplexOutput, Format, Process, WPSRequest
from pywps.response.execute import ExecuteResponse
from shapely import box

from wrfhydro import tasks
from src.config import EnvVariable as EnvVar


class FloodScenarioProcessService(Process):
    """Class representing a WebProcessingService process for creating a flooding scenario"""

    # pylint: disable=too-few-public-methods

    def __init__(self) -> None:
        """Define inputs and outputs of the WPS process, and assign process handler."""
        # Create bounding box WPS inputs
        inputs = [
            BoundingBoxInput("bboxIn", "Area of Interest", crss=["epsg:4326"]),
        ]
        # Create flood inundation WPS outputs
        outputs = [
            ComplexOutput("floodDepth", "Maximum Flood Depth",
                          supported_formats=[Format("application/vnd.terriajs.catalog-member+json")]),
            ComplexOutput("floodedBuildings", "Flooded Buildings",
                          supported_formats=[Format("application/vnd.terriajs.catalog-member+json")])
        ]

        # Initialise the process
        super().__init__(
            self._handler,
            identifier="wrfhydro",
            title="Model a flood scenario using WRF-Hydro.",
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

        modelling_task = tasks.create_scenario_for_area(bounding_box.wkt)
        scenario_id = modelling_task.get()

        # Add Geoserver JSON Catalog entries to WPS response for use by Terria
        response.outputs['floodDepth'].data = json.dumps(flood_depth_catalog(scenario_id))
        response.outputs['floodedBuildings'].data = json.dumps(building_flood_status_catalog(scenario_id))


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
    gs_flood_model_workspace = f"{EnvVar.POSTGRES_DB}-wh-model-outputs"
    gs_flood_url = f"{EnvVar.GEOSERVER_HOST}:{EnvVar.GEOSERVER_PORT}/geoserver/{gs_flood_model_workspace}/ows"

    return {
        "type": "wms",
        "name": "Flood Depth",
        "url": gs_flood_url,
        "layers": f"{gs_flood_model_workspace}:output_{scenario_id}",
        "styles": "viridis_raster"
    }
