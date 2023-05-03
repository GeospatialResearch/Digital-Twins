import logging
from http.client import OK, ACCEPTED, BAD_REQUEST

import xarray
import numpy as np

from celery.result import AsyncResult
from flask import Flask, Response, jsonify, make_response, request
from flask_cors import CORS
from pyproj import Transformer
from shapely import box, Polygon

from src import tasks

# Initialise flask server object
app = Flask(__name__)
CORS(app, origins=["http://localhost:8080"])


@app.route('/health-check')
def health_check() -> Response:
    """Ping this endpoint to check that the server is up and running"""
    return Response("Healthy", OK)


@app.route('/tasks/<task_id>', methods=["GET"])
def get_status(task_id) -> Response:
    task_result = AsyncResult(task_id, app=tasks.app)
    return make_response(jsonify({
        "taskId": task_result.id,
        "taskStatus": task_result.status,
    }), OK)


@app.route('/tasks/<task_id>', methods=["DELETE"])
def remove_task(task_id) -> Response:
    task_result = AsyncResult(task_id, app=tasks.app)
    task_result.revoke()
    return make_response("Task removed", ACCEPTED)


@app.route('/model/generate', methods=["POST"])
def generate_model() -> Response:
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


def create_wkt_from_coords(lat1: float, lng1: float, lat2: float, lng2: float) -> str:
    xmin = min([lng1, lng2])
    ymin = min([lat1, lat2])
    xmax = max([lng1, lng2])
    ymax = max([lat1, lat2])
    return box(xmin, ymin, xmax, ymax).wkt

@app.route('/model/depth', methods=["GET"])
def get_depth_at_point() -> Response:
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

    ds = xarray.open_dataset("saved_to_disk_2193.nc")


    transformer = Transformer.from_crs(4326, 2193)
    y, x = transformer.transform(lat, lng)
    da = ds["h"].sel(x=x, y=y, method="nearest")

    times = da.coords['time'].values.tolist()
    depths = da.values.tolist()

    return make_response(jsonify({
        "time": times,
        "depth": depths
    }), OK)

def valid_coordinates(latitude: float, longitude: float) -> bool:
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
