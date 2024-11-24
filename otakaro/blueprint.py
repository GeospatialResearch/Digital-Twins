# -*- coding: utf-8 -*-
"""The main web application that serves the Digital Twin to the web through a Rest API."""

from http.client import OK, ACCEPTED, NOT_FOUND

from flask import Blueprint, Response, jsonify, make_response
from pywps import Service

from src.check_celery_alive import check_celery_alive
from otakaro import tasks
from otakaro.pollution_model.medusa_process_service import MedusaProcessService

otakaro_blueprint = Blueprint('otakaro', __name__)

processes = [
    MedusaProcessService()
]

process_descriptor = {process.identifier: process.abstract for process in processes}

service = Service(processes, ['src/pywps.cfg'])


@otakaro_blueprint.route('/wps', methods=['GET', 'POST'])
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


@otakaro_blueprint.route('/scenarios/medusa/<int:scenario_id>', methods=["GET"])
@check_celery_alive
def get_rainfall_information(scenario_id: int) -> Response:
    """
    Find a list of parameters below at a particular point for a given completed model output task:
        - antecedent_dry_days
        - average_rain_intensity
        - event_duration
        - rainfall_ph

    Supported methods: GET
    Required query param values: "scenario_id": str

    Parameters
    ----------
    scenario_id: int
        The scenario ID of the pollution model run

    Returns
    -------
    Response
        Returns JSON response in the form below:
        {
            "antecedent_dry_days": int,
            "average_rain_intensity": int,
            "event_duration": int,
            "rainfall_ph": int
            "created_at": datetime.datetime,
            "geometry": polygon
        }
        representing the values for the given point.
    """
    # Get medusa rainfall information
    medusa_rainfall_dictionary = tasks.retrieve_medusa_input_parameters.delay(scenario_id).get()

    # Check if the scenario exists
    if medusa_rainfall_dictionary is None:
        return make_response(f"Could not find rainfall scenario {scenario_id}", NOT_FOUND)
    else:
        return make_response(jsonify(medusa_rainfall_dictionary), OK)


@otakaro_blueprint.route('/surface-water-sites/update', methods=["POST"])
@check_celery_alive
def refresh_surface_water_data_sources() -> Response:
    """
    Update surface water site data to the most recent.
    Fetch surface water site data from ECAN and store it in the database.
    Needs to be run periodically so that the surface water site data is up to date.
    Supported methods: POST

    Returns
    -------
    Response
        ACCEPTED is the expected response. Response body contains Celery taskId.
    """
    # Start task to refresh surface water sites
    task = tasks.refresh_surface_water_sites.delay()
    # Return HTTP Response with task id so it can be monitored with get_status(taskId)
    return make_response(
        jsonify({"taskId": task.id}),
        ACCEPTED
    )
