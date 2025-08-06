# -*- coding: utf-8 -*-
# Copyright © 2021-2025 Geospatial Research Institute Toi Hangarau
# LICENSE: https://github.com/GeospatialResearch/Digital-Twins/blob/master/LICENSE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""The main web application that serves the Digital Twin to the web through a Rest API."""

import logging
from http.client import OK

from flask import Flask, jsonify, make_response, Response
from flask_cors import CORS
from flask_swagger_ui import get_swaggerui_blueprint

from floodresilience.blueprint import flood_resilience_blueprint
from src.check_celery_alive import check_celery_alive
from src.geoserver import get_terria_catalog

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


@app.route('/terria-catalog.json')
def terria_catalog() -> Response:
    """
    Returns a terria catalog that includes entries for static files and input layers from geoserver.
    Supported methods: GET

    Returns
    -------
    Response
        The HTTP Response. Expect OK if health check is successful
    """
    terria_catalog = get_terria_catalog()
    return make_response(jsonify(terria_catalog), OK)

# Development server
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')

# Production server
if __name__ != '__main__':
    # Set gunicorn loggers to work with flask
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)
