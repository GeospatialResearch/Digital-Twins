import io
import json
import math
import time
from threading import Thread

import geopandas as gpd
from pywps import Process, LiteralInput, LiteralOutput, UOM, ComplexInput, ComplexOutput, FORMATS, Format
from pywps.inout.literaltypes import AllowedValue, AnyValue
from pywps.validator.allowed_value import ALLOWEDVALUETYPE, RANGECLOSURETYPE

from src import tasks
from src.config import EnvVariable
from src.digitaltwin.utils import LogLevel


class MedusaProcessService(Process):
    def __init__(self):
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
        super(MedusaProcessService, self).__init__(
            self._handler,
            identifier="medusa",
            title="Medusa",
            inputs=inputs,
            outputs=outputs,
            store_supported=True
        )

    def _handler(self, request, response):
        antecedent_dry_days = request.inputs['antecedentDryDays'][0].data
        average_rain_intensity = request.inputs['averageRainIntensity'][0].data
        event_duration = request.inputs['eventDuration'][0].data
        area_of_interest = gpd.GeoDataFrame.from_file("selected_polygon.geojson")

        aoi_wkt = area_of_interest.to_crs(4326).geometry[0].wkt
        medusa_task = tasks.run_medusa_model.delay(aoi_wkt, antecedent_dry_days, average_rain_intensity, event_duration)
        scenario_id = medusa_task.get()

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

# run_medusa_2.main(
#     selected_polygon_gdf=sample_polygon,
#     log_level=LogLevel.DEBUG,
#     antecedent_dry_days=1,
#     average_rain_intensity=1,
#     event_duration=1,
#     rainfall_ph=7
# )
