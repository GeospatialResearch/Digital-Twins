import logging
from http.client import OK, ACCEPTED

from celery.result import AsyncResult
from flask import Flask, Response, jsonify, make_response, request
from flask_cors import CORS
from src import tasks

# Initialise flask server object
app = Flask(__name__)
CORS(app, origins=["http://localhost:8080"])


@app.route('/health-check')
def health_check() -> Response:
    """Ping this endpoint to check that the server is up and running"""
    return Response("Healthy", OK)


@app.route('/tasks', methods=["POST"])
def run_task() -> Response:
    print('heh')
    content = request.json
    numbers = content["numbers"]
    task = tasks.add.delay(numbers)
    return make_response(
        jsonify({"task_id": task.id}),
        ACCEPTED
    )


@app.route('/tasks/<task_id>', methods=["GET"])
def get_status(task_id) -> Response:
    task_result = AsyncResult(task_id, app=tasks.app)
    return make_response({
        "task_id": task_id,
        "task_status": task_result.status,
        "task_result": task_result.result
    },
        OK
    )


# Development server
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')

# Production server
if __name__ != '__main__':
    # Set gunicorn loggers to work with flask
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)
