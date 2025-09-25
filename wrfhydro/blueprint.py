"""Endpoints and flask configuration for running WRF-Hydro module within the digital twin"""

from flask import Blueprint
from pywps import Service

from wrfhydro.scenario.flood_scenario_process_service import FloodScenarioProcessService
from src.check_celery_alive import check_celery_alive

wrf_hydro_blueprint = Blueprint('wrfhydro', __name__)
processes = [
    FloodScenarioProcessService()
]

process_descriptor = {process.identifier: process.abstract for process in processes}

service = Service(processes, ['src/pywps.cfg'])


@wrf_hydro_blueprint.route('/wps', methods=['GET', 'POST'])
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
