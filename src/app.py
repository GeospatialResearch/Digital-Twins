import logging
from http.client import OK, ACCEPTED

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

    def get_recursive_children_status(children):
        if children is None:
            return []
        statuses = []
        for child in children:
            child_status = status_as_dict(child)
            child_status["children"] = get_recursive_children_status(child.children)
            statuses.append(child_status)
        return statuses

    task_result = AsyncResult(task_id, app=tasks.app)
    status_dict = status_as_dict(task_result)
    status_dict["children"] = get_recursive_children_status(task_result.children)
    return make_response(status_dict, OK)


@app.route('/generate-model', methods=["POST"])
def generate_model() -> Response:
    task = tasks.create_model_for_area.delay()
    return make_response(
        jsonify({"task_id": task.id}),
        ACCEPTED
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
