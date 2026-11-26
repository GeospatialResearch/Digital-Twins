# -*- coding: utf-8 -*-
# Copyright © 2021-2026 Geospatial Research Institute Toi Hangarau
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
from types import ModuleType
from typing import Callable, Iterable

from flask import Flask, jsonify, make_response, Response
from flask_cors import CORS
from flask_swagger_ui import get_swaggerui_blueprint
from werkzeug.middleware.dispatcher import DispatcherMiddleware

from eddie.check_celery_alive import check_celery_alive
from eddie.config import EnvVariable
from eddie.discover_plugins import plugin_contribution
from eddie.geoserver import get_terria_catalog
from eddie.tasks import eddie_plugins
from eddie.wps import build_service

# Initialise flask server object
app = Flask(__name__)
CORS(app, origins=EnvVariable.EDDIE_CORS_ORIGINS)

# Serve API documentation. The page's links are relative to /swagger/, so they also work under a path prefix.
SWAGGER_URL = "/swagger"
API_URL = "../static/api_documentation.yml"
swagger_ui_blueprint = get_swaggerui_blueprint(
    ".",
    API_URL,
    config={"app_name": EnvVariable.EDDIE_INSTANCE_TITLE}
)
app.register_blueprint(swagger_ui_blueprint, url_prefix=SWAGGER_URL)

for plugin in eddie_plugins.values():
    blueprint = plugin_contribution(plugin, "blueprint")
    if isinstance(blueprint, ModuleType):  # Older layout: <plugin>/blueprint.py holding a `blueprint` attribute
        blueprint = blueprint.blueprint
    if blueprint is None:
        continue
    app.register_blueprint(blueprint)


def with_cors(wsgi_app: Callable, origins: Iterable[str] = ("*",)) -> Callable:
    """
    Add CORS headers to a WSGI app that runs outside Flask, so `CORS(app)` never sees its responses.
    Echoes an allowed `Origin` back, like flask-cors does, and answers the browser's OPTIONS preflight itself.

    Parameters
    ----------
    wsgi_app : Callable
        The WSGI app to wrap, here the PyWPS Service.
    origins : Iterable[str]
        The origins allowed to read responses; "*" allows any.

    Returns
    -------
    Callable
        A WSGI app that serves `wsgi_app` with CORS headers.
    """
    origins = {origin.lower() for origin in origins}  # Origins are case-insensitive, as in flask-cors

    def cors_app(environ: dict, start_response: Callable) -> Iterable[bytes]:
        """
        Serve one request through `wsgi_app`, adding CORS headers when the request's origin is allowed.

        Parameters
        ----------
        environ : dict
            The WSGI environment of the request.
        start_response : Callable
            The WSGI `start_response` callable.

        Returns
        -------
        Iterable[bytes]
            The response body.
        """
        origin = environ.get("HTTP_ORIGIN")
        if not origin or not ("*" in origins or origin.lower() in origins):
            return wsgi_app(environ, start_response)
        cors_headers = [("Access-Control-Allow-Origin", origin), ("Vary", "Origin")]
        if environ["REQUEST_METHOD"] == "OPTIONS":
            start_response("200 OK", cors_headers + [
                ("Access-Control-Allow-Methods", "GET, POST"),
                ("Access-Control-Allow-Headers", environ.get("HTTP_ACCESS_CONTROL_REQUEST_HEADERS", "")),
            ])
            return [b""]
        return wsgi_app(environ, lambda status, headers, exc_info=None: start_response(
            status, headers + cors_headers, exc_info))

    return cors_app


# Core owns the single PyWPS Service/`/wps` route; plugins only contribute `processes`
# and must not define their own `/wps` route or Service.
# Mounted beside Flask, so PyWPS sees its own paths (/wps/processes reaches it as /processes); `with_cors` adds
# the CORS headers that `CORS(app)` can't, so browser clients such as TerriaJS on another origin can read /wps.
wps_service = build_service()
app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {"/wps": with_cors(wps_service, EnvVariable.EDDIE_CORS_ORIGINS)})


@app.route('/', methods=['GET'])
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


@app.route('/health-check', methods=['GET'])
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


@app.route('/terria-catalog.json', methods=['GET'])
def terria_catalog() -> Response:
    """
    Return a terria catalog of the GeoServer workspace layers and every plugin's catalog() groups.
    Supported methods: GET

    Returns
    -------
    Response
        The HTTP Response. Expect OK with the Terria JSON catalog.
    """
    catalog = get_terria_catalog(eddie_plugins.values())
    return make_response(jsonify(catalog), OK)


# Development server
if __name__ == '__main__':
    app.run(debug=True, host='localhost')

# Production server
if __name__ != '__main__':
    # Set gunicorn loggers to work with flask
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)
