# # -*- coding: utf-8 -*-
"""Defines PyWPS WebProcessingService process for marking points and calculating polygon areas."""

import json

import geopandas as gpd
from pywps import Process, Format, ComplexInput, LiteralOutput, WPSRequest
from pywps.response.execute import ExecuteResponse


class GeometryProcessService(Process):
    """Class representing a WebProcessingService process for marking points and calculating polygon areas."""

    def __init__(self) -> None:
        """Define inputs and outputs of the WPS process, and assign process handler."""
        # Create point or polygon WPS inputs
        inputs = [
            ComplexInput('location', 'Location',
                         supported_formats=[
                             Format(mime_type='application/vnd.geo+json',
                                    schema='http://geojson.org/geojson-spec.html#geojson')],
                         workdir='workdir'
                         )
        ]
        # Create lat and lon or area WPS outputs
        outputs = [
            LiteralOutput('details', 'Details', data_type='string')
        ]

        # Initialise the process
        super().__init__(
            self._handler,
            identifier='geometry',
            title="Mark Points and Calculate Polygon Areas",
            inputs=inputs,
            outputs=outputs
        )

    @staticmethod
    def _handler(request: WPSRequest, response: ExecuteResponse) -> None:
        """
        Process handler for marking points and calculating polygon areas.

        Parameters
        ----------
        request : WPSRequest
            The WPS request, containing input parameters.
        response : ExecuteResponse
            The WPS response, containing output data.
        """
        # Get the location input (GeoJSON string) from the request
        layer_input = request.inputs["location"][0].data
        # Parse the GeoJSON string into a dictionary
        layer_json = json.loads(layer_input)

        try:
            # Get the geometry type of the feature
            geom_type = layer_json["features"][0]["geometry"]["type"]
        except IndexError:
            # Set the geometry type to 'Unknown' if it is not found or an error occurs
            geom_type = "Unknown"

        # Handle the case when the geometry type is a Point
        if geom_type == "Point":
            # Extract coordinates from the Point geometry
            coords = layer_json["features"][0]["geometry"]["coordinates"]
            longitude, latitude = coords[0], coords[1]
            # Format coordinates
            display_lat = f"{latitude:.5f}"
            display_lon = f"{longitude:.5f}"
            # Prepare and assign the formatted coordinates for display
            details = (
                f"Lat: {display_lat}<br>"
                f"Lon: {display_lon}"
            )
            response.outputs["details"].data = details

        # Handle the case when the geometry type is a Polygon or MultiPolygon
        elif geom_type in ["Polygon", "MultiPolygon"]:
            # Load the GeoJSON data into a GeoDataFrame and transform it to the desired CRS
            layer_gdf = gpd.read_file(layer_input).to_crs(epsg=2193)
            # Calculate area in square metres and square kilometres
            area_sqm = layer_gdf.geometry[0].area
            area_sqkm = area_sqm / 1000000
            # Format areas
            display_area_sqm = f"{area_sqm:.2f} m²"
            display_area_sqkm = f"{area_sqkm:.5f} km²"
            # Prepare and assign the formatted areas for display.
            # Display the area in square meters
            details = f"Area {display_area_sqm}<br>"
            # Append the area in square kilometers for display if it is large enough
            if area_sqkm >= 0.01:
                details += f"Area {display_area_sqkm}"
            response.outputs["details"].data = details

        # Handle the case when the geometry type is unknown or unsupported
        else:
            details = '<span style="color: lightgreen;">Please select an existing polygon.</span>'
            response.outputs["details"].data = details
