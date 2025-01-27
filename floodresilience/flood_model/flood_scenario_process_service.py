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

from geopandas import GeoDataFrame
from pywps import BoundingBoxInput, Process, LiteralInput, LiteralOutput, WPSRequest
from pywps.inout.literaltypes import AnyValue
from pywps.response.execute import ExecuteResponse
from shapely import box


class FloodScenarioProcessService(Process):
    """Class representing a WebProcessingService process for creating a flooding scenario"""

    def __init__(self) -> None:
        """Define inputs and outputs of the WPS process, and assign process handler."""
        # Create bounding box WPS inputs
        inputs = [
            BoundingBoxInput("bboxIn", "Area of Interest", crss=["epsg:4326"]),
            LiteralInput("projYear", "Projected Year", data_type="integer", allowed_values=[x for x in range(2026, 2151)]),
            LiteralInput("percentile", "Percentile", data_type="integer", allowed_values=[17, 50, 83], default=50),
            LiteralInput("sspScenario", "SSP Scenario", data_type="string", allowed_values=[
                "SSP1-1.9",
                "SSP1-2.6",
                "SSP2-4.5",
                "SSP3-7",
                "SSP5-8.5"
            ], default="SSP2-4.5"),

        ]
        # Create area WPS outputs
        outputs = [
            LiteralOutput("area", "Area", data_type="string")
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
        # Create GeoDataFrame with unit of measurement in metres.
        gdf = GeoDataFrame(index=[0], crs="epsg:4326", geometry=[bounding_box]).to_crs(epsg=2193)

        # Calculate area in square metres
        area = gdf.geometry[0].area
        # Format area
        display_area = f"{area:.0f} m²"
        response.outputs['area'].data = display_area
