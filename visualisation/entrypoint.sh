#!/bin/bash

# Used by docker to import environment variables into a docker container without baking them into the image

ROOT_DIR=/app
# Find the list of VUE_APP_ variables in the environment variables
VUE_ENV_VARS=$(printenv | grep -o "VUE_APP_\w*")

echo "Replacing env constants in JS"
echo "Env constants = ${VUE_ENV_VARS}"
for FILE in "$ROOT_DIR"/js/app.*.js* "$ROOT_DIR"/index.html "$ROOT_DIR"/precache-manifest*.js;
do
  echo "Processing $FILE ...";

  for VAR_NAME in $VUE_ENV_VARS;
  do
    # Use variable indirection to lookup the value of the variable
    VAR_VALUE=$(eval "echo \${$VAR_NAME}")
    # Replace all instances of the string $VAR_NAME with $VAR_VALUE, allowing it to fail if it can't find it
    sed -i 's|'"${VAR_NAME}"'|'"${VAR_VALUE}"'|g' $FILE || true
  done
done

# Run the nginx server
nginx -g 'daemon off;'
