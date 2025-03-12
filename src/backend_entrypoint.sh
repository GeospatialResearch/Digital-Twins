#!/bin/bash

# Entrypoint for the backend Flask API
# Used by docker to import environment variables into a docker container without baking them into the image.
# Used when runtime environment variables are not enough, for example, when a config file needs to be written.

# List of variables to substitute
ENV_VARS_TO_FILL='$BACKEND_HOST,$BACKEND_PORT'

# Substitute variables and save whole file to variable, sponge is not available to buffer.
SUBBED=`envsubst "$ENV_VARS_TO_FILL" < src/pywps.cfg`
# Overwrite original file.
echo "$SUBBED" > src/pywps.cfg

# Activate python virtual environment
source /venv/bin/activate
# Run production HTTP server with threads (gevent) with an extended timeout
gunicorn --bind 0.0.0.0:5000 src.app:app


