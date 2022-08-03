import logging
from http.client import OK

from flask import Flask, Response
from flask_cors import CORS

from .static_boundary_conditions import vector_blueprint

# Initialise flask server object
app = Flask(__name__)

# Set up Cross-Origin policy
CORS(app, origins=["http://localhost:8080"])

# Register modules
app.register_blueprint(vector_blueprint)


@app.route('/health-check')
def health_check() -> Response:
    """Ping this endpoint to check that the server is up and running"""
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
