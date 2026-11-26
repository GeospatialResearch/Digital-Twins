#!/bin/bash

# Entrypoint for the backend Flask API
# Used by docker to import environment variables into a docker container without baking them into the image.
# Used when runtime environment variables are not enough, for example, when a config file needs to be written.

# Default matches EnvVariable.EDDIE_INSTANCE_TITLE in src/eddie/config.py
export EDDIE_INSTANCE_TITLE="${EDDIE_INSTANCE_TITLE:-Environmental Digital Data Intelligence Engine (EDDIE) Core}"

# The backend's public root: <EDDIE_PUBLIC_URL>/api behind an ingress, else BACKEND_HOST[:BACKEND_PORT]
PUBLIC_API=${EDDIE_PUBLIC_URL:+${EDDIE_PUBLIC_URL%/}/api}
export BACKEND_URL=${PUBLIC_API:-$BACKEND_HOST${BACKEND_PORT:+:$BACKEND_PORT}}

# List of variables to substitute
ENV_VARS_TO_FILL='$BACKEND_URL,$EDDIE_INSTANCE_TITLE'

# Substitute variables and save whole file to variable, sponge is not available to buffer.
SUBBED=`envsubst "$ENV_VARS_TO_FILL" < src/pywps.cfg`
# Overwrite original file.
echo "$SUBBED" > src/pywps.cfg

# Activate python virtual environment
source /venv/bin/activate
# Run production HTTP server with threads (gevent) with an extended timeout
gunicorn --bind 0.0.0.0:5000 --timeout 600 -k gevent eddie.app:app


