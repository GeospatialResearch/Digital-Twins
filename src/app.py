"""
The main web application that serves the Digital Twin to the web through a Rest API.
"""
import logging
from http.client import OK, ACCEPTED, BAD_REQUEST

from celery import result, states
from flask import Flask, Response, jsonify, make_response, request
from flask_cors import CORS
from shapely import box

from src import tasks
from src.config import get_env_variable
from src.flood_model.bg_flood_model import model_output_from_db_by_id

# Initialise flask server object
app = Flask(__name__)
CORS(app, origins=["http://localhost:8080"])


@app.route('/health-check')
def health_check() -> Response:
    """
    Ping this endpoint to check that the server is up and running
    Supported methods: GET

    Returns
    -------
    Response
        The HTTP Response. Expect OK if health check is successful
    """
    return Response("Healthy", OK)


@app.route('/tasks/<task_id>', methods=["GET"])
def get_status(task_id) -> Response:
    """
    Retrieves status of a particular Celery backend task.
    Supported methods: GET

    Parameters
    ----------
    task_id : str
        The id of the Celery task to retrieve status from

    Returns
    -------
    Response
        JSON response containing taskStatus
    """
    task_result = result.AsyncResult(task_id, app=tasks.app)
    status = task_result.status
    task_value = task_result.get() if status == states.SUCCESS else None
    return make_response(jsonify({
        "taskId": task_result.id,
        "taskStatus": status,
        "taskValue": task_value
    }), OK)


@app.route('/tasks/<task_id>', methods=["DELETE"])
def remove_task(task_id) -> Response:
    """
    Deletes and stops a particular Celery backend task.
    Supported methods: DELETE

    Parameters
    ----------
    task_id : str
        The id of the Celery task to remove

    Returns
    -------
    Response
        ACCEPTED is the expected response
    """
    task_result = result.AsyncResult(task_id, app=tasks.app)
    task_result.revoke()
    return make_response("Task removed", ACCEPTED)


@app.route('/models/generate', methods=["POST"])
def generate_model() -> Response:
    """
    Generates a flood model for a given area.
    Supported methods: POST
    POST values: {"bbox": {"lat1": number, "lat2": number, "lng1": number, "lng2": number}}

    Returns
    -------
    Response
        ACCEPTED is the expected response. Response body contains Celery taskId
    """
    try:
        bbox = request.get_json()["bbox"]
        lat1 = float(bbox.get("lat1"))
        lng1 = float(bbox.get("lng1"))
        lat2 = float(bbox.get("lat2"))
        lng2 = float(bbox.get("lng2"))
    except ValueError:
        return make_response(
            "JSON values for bbox: lat1, lng1, lat2, lng2 must be valid floats", BAD_REQUEST
        )
    if any(coord is None for coord in [lat1, lng1, lat2, lng2]):
        return make_response("JSON body parameters bbox: {lat1, lng1, lat2, lng2} mandatory", BAD_REQUEST)
    if not valid_coordinates(lat1, lng1) or not valid_coordinates(lat2, lng2):
        return make_response("lat & lng must fall in the range -90 < lat <= 90, -180 < lng <= 180", BAD_REQUEST)
    if (lat1, lng1) == (lat2, lng2):
        return make_response("lat1, lng1 must not equal lat2, lng2", BAD_REQUEST)

    bbox_wkt = create_wkt_from_coords(lat1, lng1, lat2, lng2)
    task = tasks.create_model_for_area(bbox_wkt)

    return make_response(
        jsonify({"taskId": task.id}),
        ACCEPTED
    )


@app.route('/models/<model_id>', methods=["GET"])
def get_wfs_layer_from_model(model_id: int):
    layer_name = model_output_from_db_by_id(model_id).stem
    gs_host = get_env_variable("GEOSERVER_HOST")
    gs_port = get_env_variable("GEOSERVER_PORT")
    return make_response(jsonify({
        "url": f"{gs_host}:{gs_port}/geoserver/dt-model-outputs/wms",
        "layers": f"dt-model-outputs:{layer_name}"
    }), OK)


def create_wkt_from_coords(lat1: float, lng1: float, lat2: float, lng2: float) -> str:
    """
    Takes two points and creates a wkt bbox string from them

    Parameters
    ----------
    lat1 : float
        latitude of first point
    lng1: float
        longitude of first point
    lat2 : float
        latitude of second point
    lng2: float
        longitude of second point

    Returns
    -------
    str
        bbox in wkt form generated from the two coordinates
    """
    xmin = min([lng1, lng2])
    ymin = min([lat1, lat2])
    xmax = max([lng1, lng2])
    ymax = max([lat1, lat2])
    return box(xmin, ymin, xmax, ymax).wkt


@app.route('/tasks/<task_id>/model/depth', methods=["GET"])
def get_depth_at_point(task_id: str) -> Response:
    try:
        lat = request.args.get("lat", type=float)
        lng = request.args.get("lng", type=float)
    except ValueError:
        return make_response("Query parameters lat & lng must be valid floats", BAD_REQUEST)
    if lat is None or lng is None:
        return make_response("Query parameters mandatory: lat & lng", BAD_REQUEST)
    if not valid_coordinates(lat, lng):
        return make_response("Query parameters lat & lng must fall in the range -90 < lat <= 90, -180 < lng <= 180",
                             BAD_REQUEST)
    model_task_result = result.AsyncResult(task_id, app=tasks.app)
    status = model_task_result.status
    if status != states.SUCCESS:
        return make_response(f"Task {task_id} has status {status}, not {states.SUCCESS}", BAD_REQUEST)

    model_id = model_task_result.get()
    depth_task = tasks.get_depth_by_time_at_point.delay(model_id, lat, lng)
    depths, times = depth_task.get()

    return make_response(jsonify({
        'depth': depths,
        'time': times
    }), OK)


def valid_coordinates(latitude: float, longitude: float) -> bool:
    """
    Validates coordinates are in the valid range of WGS84
    (-90 < latitude <= 90) and (-180 < longitude <= 180)

    Parameters
    ----------
    latitude : float
        The latitude part of the coordinate
    longitude : float
        The longitude part of the coordinate

    Returns
    -------
    bool
        True if both latitude and longitude are within their valid ranges.
    """
    return (-90 < latitude <= 90) and (-180 < longitude <= 180)


# Development server
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')

# Production server
if __name__ != '__main__':
    # Set gunicorn loggers to work with flask
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)
