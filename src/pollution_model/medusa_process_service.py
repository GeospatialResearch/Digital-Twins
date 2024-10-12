from pywps import Process, LiteralInput, LiteralOutput, UOM


class MedusaProcessService(Process):
    def __init__(self):
        inputs = [
            LiteralInput("antecedentDryDays", "Antecedent Dry Days", data_type='float'),
            LiteralInput("averageRainIntensity", "Average Rain Intensity", data_type='float'),
            LiteralInput("eventDuration", "Event Duration", data_type='float'),
            LiteralInput("rainfallPh", "Rainfall pH", data_type='float'),
        ]
        outputs = [
            LiteralOutput("output", "Output", data_type='float')
        ]
        super(MedusaProcessService, self).__init__(
            self._handler,
            identifier="medusa",
            title="Medusa",
            inputs=inputs,
            outputs=outputs,
        )

    def _handler(self, request, response):
        response.outputs['output'].data = request.inputs['antecedentDryDays'][0].data
        response.outputs['output'].uom = UOM('metre')


# run_medusa_2.main(
#     selected_polygon_gdf=sample_polygon,
#     log_level=LogLevel.DEBUG,
#     antecedent_dry_days=1,
#     average_rain_intensity=1,
#     event_duration=1,
#     rainfall_ph=7
# )
