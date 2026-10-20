#!/bin/bash

# Entrypoint for running a Celery worker

# Activate python virtual environment
source /venv/bin/activate

# Run health-checker application, which reports back on the health of this container.
# And in parallel run the celery workers
health-checker --listener 0.0.0.0:5001 --log-level error --script-timeout 10 --script "celery -A eddie.tasks inspect ping"  \
& celery -A eddie.tasks worker -P threads --loglevel=INFO
