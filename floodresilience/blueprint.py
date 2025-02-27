"""Endpoints and flask configuration for the Flood Resilience Digital Twin"""

from flask import Blueprint
from pywps import Service

from floodresilience.flood_model.flood_scenario_process_service import FloodScenarioProcessService
from src.check_celery_alive import check_celery_alive

flood_resilience_blueprint = Blueprint('floodresilience', __name__)
processes = [
    FloodScenarioProcessService()
]

process_descriptor = {process.identifier: process.abstract for process in processes}

service = Service(processes, ['src/pywps.cfg'])


@flood_resilience_blueprint.route('/wps', methods=['GET', 'POST'])
@check_celery_alive
def wps() -> Service:
    """
    End point for OGC WebProcessingService spec, allowing clients such as TerriaJS to request processing.

    Returns
    -------
    Service
        The PyWPS WebProcessing Service instance
    """
    return service
