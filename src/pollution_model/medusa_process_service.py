import json
import math

from pywps import Process, LiteralInput, LiteralOutput, UOM, ComplexInput, ComplexOutput, FORMATS, Format
from pywps.inout.literaltypes import AllowedValue, AnyValue
from pywps.validator.allowed_value import ALLOWEDVALUETYPE, RANGECLOSURETYPE


class MedusaProcessService(Process):
    def __init__(self):
        inputs = [
            LiteralInput("antecedentDryDays", "Antecedent Dry Days", data_type='float', allowed_values=AnyValue()),
            LiteralInput("averageRainIntensity", "Average Rain Intensity (mm/hour)", data_type='float', allowed_values=AnyValue()),
            LiteralInput("eventDuration", "Event Duration (hours)", data_type='float', allowed_values=AnyValue()),
        ]
        outputs = [
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
        response.outputs['roofs'].data = json.dumps({
            "type": "geojson",
            "url": "http://localhost:5000/outputs/MEDUSA_Roofs.geojson",
            "name": "MEDUSA Roof Surfaces",
            "id": "some unique I111D"
        })
        response.outputs['roads'].data = json.dumps({
            "type": "geojson",
            "url": "http://localhost:5000/outputs/MEDUSA_Roads.geojson",
            "name": "MEDUSA Road Surfaces",
            "id": "some unique I111D2"
        })


# run_medusa_2.main(
#     selected_polygon_gdf=sample_polygon,
#     log_level=LogLevel.DEBUG,
#     antecedent_dry_days=1,
#     average_rain_intensity=1,
#     event_duration=1,
#     rainfall_ph=7
# )
