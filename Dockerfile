FROM continuumio/miniconda3:23.10.0-1 AS build
# Miniconda layer for building conda environment
WORKDIR /app

# Install mamba for faster conda solves
RUN conda install -c conda-forge mamba

# Create Conda environment
COPY environment.yml .
RUN mamba env create -f environment.yml

# Make RUN commands use the new environment:
SHELL ["conda", "run", "-n", "digitaltwin", "/bin/bash", "-c"]

# Test that conda environment worked successfully
RUN echo "Check GeoFabrics is installed to test environment"
RUN python -c "import geofabrics"

# Pack conda environment to be shared to runtime image
RUN conda-pack --ignore-missing-files -n digitaltwin -o /tmp/env.tar \
  && mkdir /venv \
  && cd /venv \
  && tar xf /tmp/env.tar \
  && rm /tmp/env.tar
RUN /venv/bin/conda-unpack


FROM lparkinson/bg_flood:v0.9 AS runtime-base
# BG_Flood stage for running the digital twin. Reduces image size significantly if we use a multi-stage build
WORKDIR /app

USER root

# Install dependencies
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl acl \
# Cleanup image and remove junk
 && rm -fr /var/lib/apt/lists/* \
# Remove unused packages. Keep curl for health checking in docker-compose
 && apt-get purge -y ca-certificates

# Install health-checker tool that allows us to run commands when checking root endpoint to check if service is available
ADD --chmod=555 https://github.com/gruntwork-io/health-checker/releases/download/v0.0.8/health-checker_linux_amd64 \
 /usr/local/bin/health-checker

# Create stored data dir inside image, in case it does not get mounted (such as when deploying on AWS)
RUN mkdir /stored_data \
    && setfacl -R -d -m u:nonroot:rwx /stored_data \
    && setfacl -R -m u:nonroot:rwx /stored_data \
    && mkdir /stored_data/geoserver

# Copy python virtual environment from build layer
COPY --chown=root:root --chmod=555 --from=build /venv /venv
USER nonroot

# Copy source files and essential runtime files
COPY --chown=root:root --chmod=444 selected_polygon.geojson .
COPY --chown=nonroot:nonroot --chmod=644 instructions.json .
COPY --chown=root:root --chmod=555 src/ src/


FROM runtime-base AS backend
# Image build target for backend
# Using separate build targets for each image because the Orbica platform does not allow for modifying entrypoints
# and using multiple dockerfiles was creating increase complexity problems keeping things in sync

# Create PyWPS required logging and output directories
SHELL ["/bin/bash", "-c"]
USER root
RUN <<EOF
for NEW_DIRECTORY in "outputs" "workdir" "logs"
do
    mkdir "$NEW_DIRECTORY"
    setfacl -R -d -m u:nonroot:rwx "$NEW_DIRECTORY"
    setfacl -R -m u:nonroot:rwx "$NEW_DIRECTORY"
done
EOF
USER nonroot

EXPOSE 5000

SHELL ["/bin/bash", "-c"]
ENTRYPOINT source /venv/bin/activate && \
           gunicorn --bind 0.0.0.0:5000 --timeout 600 -k gevent  src.app:app


FROM runtime-base AS celery_worker
# Image build target for celery_worker

EXPOSE 5001

SHELL ["/bin/bash", "-c"]
# Activate environment and run the health-checker in background and celery worker in foreground
ENTRYPOINT source /venv/bin/activate && \
           health-checker --listener 0.0.0.0:5001 --log-level error --script-timeout 10 \
             --script "celery -A src.tasks inspect ping"  & \
           source /venv/bin/activate && \
           celery -A src.tasks worker -P threads --loglevel=INFO

FROM docker.osgeo.org/geoserver:2.21.2 AS geoserver

RUN addgroup --system nonroot \
    && adduser --system --group nonroot \
    && chgrp -R nonroot $GEOSERVER_DATA_DIR \
    && chmod -R g+rwx $GEOSERVER_DATA_DIR

SHELL ["/bin/sh", "-c"]
ENTRYPOINT /opt/startup.sh

