#!/bin/bash

# Used by docker to import environment variables into a docker container without baking them into the image.
# Used when runtime environment variables are not enough, for example, when a config file needs to be written.

# List of variables to substitute
ENV_VARS_TO_FILL='$CESIUM_ACCESS_TOKEN'

# Substitute variables and save whole file to variable, sponge is not available to buffer.
SUBBED=`envsubst "$ENV_VARS_TO_FILL" < wwwroot/config.json`
# Overwrite original file.
echo "$SUBBED" > wwwroot/config.json

# Run original terria startup command
node ./node_modules/terriajs-server/lib/app.js --config-file serverconfig.json
