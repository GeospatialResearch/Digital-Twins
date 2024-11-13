"""Defines PyWPS WebProcessingService process for running MEDUSA model"""
import json

import geopandas as gpd
from pywps import ComplexOutput, Format, LiteralInput, Process, WPSRequest
from pywps.inout.literaltypes import AnyValue
from pywps.response.execute import ExecuteResponse

from src import tasks


class MedusaProcessService(Process):
    """Class representing a WebProcessingService process for MEDUSA pollution model."""

    def __init__(self) -> None:
        """Define inputs and outputs of the WPS process, and assign process handler."""
        inputs = [
            LiteralInput("antecedentDryDays", "Antecedent Dry Days", data_type='float', allowed_values=AnyValue()),
            LiteralInput("averageRainIntensity", "Average Rain Intensity (mm/hour)", data_type='float',
                         allowed_values=AnyValue()),
            LiteralInput("eventDuration", "Event Duration (hours)", data_type='float', allowed_values=AnyValue()),
        ]
        outputs = [
            ComplexOutput("roofs", "Output",
                          supported_formats=[Format("application/vnd.terriajs.catalog-member+json")]),
            ComplexOutput("roads", "Output", supported_formats=[Format("application/vnd.terriajs.catalog-member+json")])
        ]
        super().__init__(
            self._handler,
            identifier="medusa",
            title="Medusa",
            inputs=inputs,
            outputs=outputs,
            store_supported=True
        )

    def _handler(self, request: WPSRequest, response: ExecuteResponse) -> None:
        """
        Process handler for MEDUSA, runs the MEDUSA model using a Celery task.

        Parameters
        ----------
        request : WPSRequest
            The WPS request, containing input parameters.
        response : ExecuteResponse
            The WPS response, containing output data.
        """
        # Read input parameters from request
        antecedent_dry_days = request.inputs['antecedentDryDays'][0].data
        average_rain_intensity = request.inputs['averageRainIntensity'][0].data
        event_duration = request.inputs['eventDuration'][0].data
        # Read area of interest from file
        area_of_interest = gpd.GeoDataFrame.from_file("selected_polygon.geojson")

        # Serialise area_of_interest in WKT str format, for sending to Celery
        aoi_wkt = area_of_interest.to_crs(4326).geometry[0].wkt
        # Send MEDUSA task to celery
        medusa_task = tasks.run_medusa_model.delay(aoi_wkt, antecedent_dry_days, average_rain_intensity, event_duration)
        # Wait until celery task is completed
        scenario_id = medusa_task.get()

        # Add Geoserver JSON Catalog entries to WPS response for use by Terria
        response.outputs['roofs'].data = json.dumps({
            "type": "wfs",
            "name": "MEDUSA Roof Surfaces",
            "url": "http://localhost:8088/geoserver/db-pollution/ows",
            "typeNames": "db-pollution:medusa2_model_output_buildings",
            "parameters": {
                "cql_filter": f"scenario_id={scenario_id}",
            },
            "maxFeatures": 300000
        })
        response.outputs['roads'].data = json.dumps({
            "type": "wfs",
            "name": "MEDUSA Road Surfaces",
            "url": "http://localhost:8088/geoserver/db-pollution/ows",
            "typeNames": "db-pollution:medusa2_model_output_roads",
            "parameters": {
                "cql_filter": f"scenario_id={scenario_id}",
            },
            "maxFeatures": 10000
        })
