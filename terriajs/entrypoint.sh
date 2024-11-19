#!/bin/bash

# Used by docker to import environment variables into a docker container without baking them into the image.
# Used when runtime environment variables are not enough, for example, when a config file needs to be written.

# List of variables to substitute
ENV_VARS_TO_FILL='$CESIUM_ACCESS_TOKEN,$BACKEND_HOST,$BACKEND_PORT'

# Substitute variables and save whole file to variable, sponge is not available to buffer.
for FILE_TO_SUB in "wwwroot/config.json" "wwwroot/init/catalog.json"
do
  SUBBED=`envsubst "$ENV_VARS_TO_FILL" < "$FILE_TO_SUB"`
  # Overwrite original file.
  echo "$SUBBED" > "$FILE_TO_SUB"
done
# Run original terria startup command
node ./node_modules/terriajs-server/lib/app.js --config-file serverconfig.json
