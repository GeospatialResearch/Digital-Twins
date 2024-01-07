#!/usr/bin/env bash

## Sets any necessary pre-requisite folders and builds/pulls docker images.
## Uses the local repository as priority over published docker images.

# Read .env file
echo "Reading .env file"
set -o allexport
source .env
set +o allexport

# Create geoserver folder that needs to be created by a user and not the Docker user
echo "Ensuring DATA_DIR_GEOSERVER ($DATA_DIR_GEOSERVER) exists"
mkdir -p "$DATA_DIR_GEOSERVER"

# Check if docker-compose command is available for compatability with different docker CLI versions
if ! command -v docker-compose &> /dev/null
then
  # If the command is not available, create an alias for it
  alias docker-compose="docker compose --compatibility $@"
fi

# Pull docker images from online where available
docker-compose pull

# Build images that are different from the online source
docker-compose build
