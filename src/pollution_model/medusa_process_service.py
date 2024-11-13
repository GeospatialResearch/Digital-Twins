import io
import json
import math
import time
from threading import Thread

import geopandas as gpd
from pywps import Process, LiteralInput, LiteralOutput, UOM, ComplexInput, ComplexOutput, FORMATS, Format
from pywps.inout.literaltypes import AllowedValue, AnyValue
from pywps.validator.allowed_value import ALLOWEDVALUETYPE, RANGECLOSURETYPE

from src.digitaltwin.utils import LogLevel
from src.pollution_model import run_medusa_2


class MedusaProcessService(Process):

    def __init__(self):
        inputs = [
            LiteralInput("antecedentDryDays", "Antecedent Dry Days", data_type='float', allowed_values=AnyValue()),
            LiteralInput("averageRainIntensity", "Average Rain Intensity (mm/hour)", data_type='float', allowed_values=AnyValue()),
            LiteralInput("eventDuration", "Event Duration (hours)", data_type='float', allowed_values=AnyValue()),
        ]
        outputs = [
            LiteralOutput("scenarioDetails", "Scenario Details", data_type='string'),
            ComplexOutput("roofs", "Output", supported_formats=[Format("application/vnd.terriajs.catalog-member+json")]),
            ComplexOutput("roads", "Output", supported_formats=[Format("application/vnd.terriajs.catalog-member+json")])
        ]
        super(MedusaProcessService, self).__init__(
            self._handler,
            identifier="medusa",
            title="Medusa",
            inputs=inputs,
            outputs=outputs,
            store_supported=True
        )

    def _handler(self, request, response):

        def format_number(number):
            """Return `number` as an int if whole, otherwise as a float."""
            return int(number) if number % 1 == 0 else float(number)

        antecedent_dry_days = request.inputs['antecedentDryDays'][0].data
        average_rain_intensity = request.inputs['averageRainIntensity'][0].data
        event_duration = request.inputs['eventDuration'][0].data
        area_of_interest = gpd.GeoDataFrame.from_file("selected_polygon.geojson")

        scenario_id = run_medusa_2.main(
            area_of_interest,
            LogLevel.DEBUG,
            antecedent_dry_days,
            average_rain_intensity,
            event_duration
        )

        scenario_details = (
            f"Antecedent Dry Days: {format_number(antecedent_dry_days)}<br>"
            f"Average Rain Intensity (mm/hour): {format_number(average_rain_intensity)}<br>"
            f"Event Duration (hours): {format_number(event_duration)}<br>"
            f"Scenario ID: {scenario_id}"
        )

        scenario_short_report = [
            {
                "name": "Scenario Details",
                "content": scenario_details,
                "show": False
            }
        ]

        response.outputs['scenarioDetails'].data = scenario_details

        response.outputs['roofs'].data = json.dumps({
            "type": "wfs",
            "name": "MEDUSA Roof Surfaces",
            "url": "http://localhost:8088/geoserver/db-pollution/ows",
            "typeNames": "db-pollution:medusa2_model_output_buildings",
            "parameters": {
                "cql_filter": f"scenario_id={scenario_id}",
            },
            "maxFeatures": 300000,
            "shortReportSections": scenario_short_report
        })

        response.outputs['roads'].data = json.dumps({
            "type": "wfs",
            "name": "MEDUSA Road Surfaces",
            "url": "http://localhost:8088/geoserver/db-pollution/ows",
            "typeNames": "db-pollution:medusa2_model_output_roads",
            "parameters": {
                "cql_filter": f"scenario_id={scenario_id}",
            },
            "maxFeatures": 10000,
            "shortReportSections": scenario_short_report
        })
