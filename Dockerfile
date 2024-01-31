FROM continuumio/miniconda3 as build
# Miniconda layer for building conda environment
WORKDIR /app

# Create Conda environment
COPY environment.yml .
RUN conda env create -f environment.yml

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


FROM lparkinson/bg_flood:v0.9 as runtime-base
# BG_Flood stage for running the digital twin. Reduces image size significantly if we use a multi-stage build
WORKDIR /app

# Install firefox browser for use within selenium
RUN apt-get update                             \
 && apt-get install -y --no-install-recommends ca-certificates curl firefox \
 && rm -fr /var/lib/apt/lists/*                \
 && curl -L https://github.com/mozilla/geckodriver/releases/download/v0.30.0/geckodriver-v0.30.0-linux64.tar.gz | tar xz -C /usr/local/bin \
 && apt-get purge -y ca-certificates curl

# Copy python virtual environment from build layer
COPY --from=build /venv /venv

# Using python virtual environment, preload selenium with firefox so that first runtime is faster.
SHELL ["/bin/bash", "-c"]
RUN source /venv/bin/activate && \
    selenium-manager --browser firefox --debug

# Copy source files and essential runtime files
COPY selected_polygon.geojson .
COPY instructions.json .
COPY src/ src/


FROM runtime-base as backend
# Image build target for backend
# Using separate build targets for each image because the Orbica platform does not allow for modifying entrypoints
# and using multiple dockerfiles was creating increase complexity problems keeping things in sync
EXPOSE 5000

SHELL ["/bin/bash", "-c"]
ENTRYPOINT source /venv/bin/activate && \
           gunicorn --bind 0.0.0.0:5000 src.app:app


FROM runtime-base as celery_worker
# Image build target for celery_worker

SHELL ["/bin/bash", "-c"]
ENTRYPOINT source /venv/bin/activate && \
           celery -A src.tasks worker -P threads --loglevel=INFO
