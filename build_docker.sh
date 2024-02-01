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

# Pull docker images from online where available
docker compose pull

# Build images that are different from the online source
docker compose build


# Save images to tar for backup in case docker goes down
echo "Saving images to fredt.tar"
docker save -o fredt.tar \
  postgis/postgis:16-3.4 \
  lparkinson/backend-flood-resilience-dt:1.0 \
  lparkinson/celery-flood-resilience-dt:1.0 \
  docker.osgeo.org/geoserver:2.21.2 \
  lparkinson/www-flood-resilience-dt:1.0 \
  redis:7 \


echo "Saving docker build dependency images to build_dep.tar"
docker save -o build_dep.tar \
  lparkinson/bg_flood:v0.9 \
  continuumio/miniconda3:23.10.0-1 \
  node:lts \
  nginx:stable
