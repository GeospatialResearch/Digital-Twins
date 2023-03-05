import logging
from http.client import OK, ACCEPTED
from typing import List

from celery.result import AsyncResult
from flask import Flask, Response, jsonify, make_response
from flask_cors import CORS

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
    def status_as_dict(result: AsyncResult) -> dict:
        return {
            "task_id": result.id,
            "task_status": result.status,
            "task_result": result.result
        }

    task_result = AsyncResult(task_id, app=tasks.app)
    status_dict = status_as_dict(task_result)
    status_dict["children"] = [status_as_dict(child) for child in task_result.children[0].children]
    return make_response(status_dict, OK)


@app.route('/generate-model', methods=["POST"])
def generate_model() -> Response:
    task = tasks.create_model_for_area.delay()
    return make_response(
        jsonify({"task_id": task.id,
                 "children": get_child_ids(task)}),
        ACCEPTED
    )


def get_child_ids(group_task) -> List[str]:
    _result, children = group_task.get()
    return [child_id for (child_id, _state), _further_children in children]


# Development server
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')

# Production server
if __name__ != '__main__':
    # Set gunicorn loggers to work with flask
    gunicorn_logger = logging.getLogger('gunicorn.error')
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)
