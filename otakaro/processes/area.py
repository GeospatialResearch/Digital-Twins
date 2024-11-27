# # -*- coding: utf-8 -*-
"""Defines PyWPS WebProcessingService process for calculating area of geometries."""

from geopandas import GeoDataFrame
from pywps import BoundingBoxInput, Process, LiteralOutput, WPSRequest
from pywps.response.execute import ExecuteResponse
from shapely import box


class BoundingBoxAreaProcess(Process):
    """Class representing a WebProcessingService process for calculating area of a bounding box"""

    def __init__(self) -> None:
        """Define inputs and outputs of the WPS process, and assign process handler."""
        # Create bounding box WPS inputs
        inputs = [
            BoundingBoxInput('bboxin', 'box in', crss=['epsg:4326'])
        ]
        # Create area WPS outputs
        outputs = [
            LiteralOutput('area', 'Area', data_type='string')
        ]

        # Initialise the process
        super().__init__(
            self._handler,
            identifier='area',
            title="Calculate the area of the polygon.",
            inputs=inputs,
            outputs=outputs,
        )

    @staticmethod
    def _handler(request: WPSRequest, response: ExecuteResponse) -> None:
        """
        Process handler for calculating bounding box area.

        Parameters
        ----------
        request : WPSRequest
            The WPS request, containing input parameters.
        response : ExecuteResponse
            The WPS response, containing output data.
        """
        # Get coordinates from bounding box input
        bounding_box_input = request.inputs['bboxin'][0]
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
