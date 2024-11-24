# -*- coding: utf-8 -*-
"""The main web application that serves the Digital Twin to the web through a Rest API."""

import logging
from http.client import OK

from flask import Flask, Response
from flask_cors import CORS
from flask_swagger_ui import get_swaggerui_blueprint
from pywps import Service

from floodresilience.blueprint import flood_resilience_blueprint
from src.check_celery_alive import check_celery_alive
from otakaro.pollution_model.medusa_process_service import MedusaProcessService
from otakaro.blueprint import otakaro_blueprint

# Initialise flask server object
app = Flask(__name__)
CORS(app)

# Serve API documentation
SWAGGER_URL = "/swagger"
API_URL = "/static/api_documentation.yml"
swagger_ui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={"app_name": "Flood Resilience Digital Twin (FReDT)"}
)
app.register_blueprint(swagger_ui_blueprint, url_prefix=SWAGGER_URL)

app.register_blueprint(flood_resilience_blueprint)
app.register_blueprint(otakaro_blueprint)

processes = [
    MedusaProcessService()
]

process_descriptor = {process.identifier: process.abstract for process in processes}

service = Service(processes, ['src/pywps.cfg'])


@app.route('/')
def index() -> Response:
    """
    Ping this endpoint to check that the flask app is running.
    Supported methods: GET

    Returns
    -------
    Response
        The HTTP Response. Expect OK if health check is successful
    """
    return Response("""
    Backend is receiving requests.
    GET /health-check to check if celery workers active.
    GET /swagger to get API documentation.
    """, OK)


@app.route('/health-check')
@check_celery_alive
def health_check() -> Response:
    """
    Ping this endpoint to check that the server is up and running.
    Supported methods: GET

    Returns
    -------
    Response
        The HTTP Response. Expect OK if health check is successful
    """
    return Response("Healthy", OK)


# Development server
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')

# Production server
if __name__ != '__main__':
    # Set gunicorn loggers to work with flask
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)
