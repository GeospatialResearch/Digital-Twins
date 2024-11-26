# -*- coding: utf-8 -*-
"""Defines PyWPS WebProcessingService process for running MEDUSA model"""

import json
from typing import Union

import geopandas as gpd
from pywps import ComplexOutput, Format, LiteralInput, LiteralOutput, Process, WPSRequest
from pywps.inout.literaltypes import AnyValue
from pywps.response.execute import ExecuteResponse

from src.config import EnvVariable as EnvVar
from otakaro import tasks


class MedusaProcessService(Process):
    """Class representing a WebProcessingService process for MEDUSA pollution model."""

    def __init__(self) -> None:
        """Define inputs and outputs of the WPS process, and assign process handler."""
        inputs = [
            LiteralInput("antecedentDryDays", "Antecedent Dry Days (number of dry days between rain events)",
                         data_type='float', allowed_values=AnyValue()),
            LiteralInput("averageRainIntensity", "Average Rain Intensity (mm/hour)",
                         data_type='float', allowed_values=AnyValue()),
            LiteralInput("eventDuration", "Event Duration (hours)",
                         data_type='float', allowed_values=AnyValue()),
        ]
        outputs = [
            LiteralOutput("scenarioDetails", "Scenario Details",
                          data_type='string'),
            ComplexOutput("roofs", "Output",
                          supported_formats=[Format("application/vnd.terriajs.catalog-member+json")]),
            ComplexOutput("roads", "Output",
                          supported_formats=[Format("application/vnd.terriajs.catalog-member+json")])
        ]
        super().__init__(
            self._handler,
            identifier="medusa",
            title="Medusa",
            inputs=inputs,
            outputs=outputs,
            store_supported=True
        )

    @staticmethod
    def _handler(request: WPSRequest, response: ExecuteResponse) -> None:
        """
        Process handler for MEDUSA, runs the MEDUSA model using a Celery task.

        Parameters
        ----------
        request : WPSRequest
            The WPS request, containing input parameters.
        response : ExecuteResponse
            The WPS response, containing output data.
        """
        def _format_number(number: float) -> Union[int, float]:
            """
            Return `number` as an int if whole, otherwise as a float.

            Parameters
            ----------
            number : float
                The number to be formatted.

            Returns
            -------
            Union[int, float]
                The formatted number, either as an int if whole or as a float.
            """
            return int(number) if number % 1 == 0 else float(number)

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

        # Create scenario details as HTML-formatted text with input values and scenario ID
        scenario_details = (
            f"Antecedent Dry Days: {_format_number(antecedent_dry_days)}<br>"
            f"Average Rain Intensity (mm/hour): {_format_number(average_rain_intensity)}<br>"
            f"Event Duration (hours): {_format_number(event_duration)}<br>"
            f"Scenario ID: {_format_number(scenario_id)}"
        )

        # Create a short report containing scenario details
        scenario_short_report = [
            {
                "name": "Scenario Details",
                "content": scenario_details,
                "show": False
            }
        ]

        # Present the user with the scenario details for visualization
        response.outputs['scenarioDetails'].data = scenario_details

        geoserver_workspace = f"{EnvVar.POSTGRES_DB}-pollution"
        geoserver_url = f"{EnvVar.GEOSERVER_HOST}:{EnvVar.GEOSERVER_PORT}/geoserver/{geoserver_workspace}/ows"

        # Add Geoserver JSON Catalog entries to WPS response for use by Terria
        response.outputs['roofs'].data = json.dumps({
            "type": "wfs",
            "name": "MEDUSA Roof Surfaces",
            "url": geoserver_url,
            "typeNames": f"{geoserver_workspace}:medusa2_model_output_buildings",
            "parameters": {
                "cql_filter": f"scenario_id={scenario_id}",
            },
            "maxFeatures": 300000,
            "defaultStyle": {
                "outline": {
                    "null": {
                        "width": 0
                    }
                }
            },
            "shortReportSections": scenario_short_report
        })
        response.outputs['roads'].data = json.dumps({
            "type": "wfs",
            "name": "MEDUSA Road Surfaces",
            "url": geoserver_url,
            "typeNames": f"{geoserver_workspace}:medusa2_model_output_roads",
            "parameters": {
                "cql_filter": f"scenario_id={scenario_id}",
            },
            "maxFeatures": 10000,
            "defaultStyle": {
                "outline": {
                    "null": {
                        "width": 0
                    }
                }
            },
            "shortReportSections": scenario_short_report
        })
