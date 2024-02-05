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

# Install firefox browser .deb (not snap) and driver (geckodriver) for use within selenium
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl wget \
 && wget -q https://packages.mozilla.org/apt/repo-signing-key.gpg -O- | tee /etc/apt/keyrings/packages.mozilla.org.asc > /dev/null \
 && echo "deb [signed-by=/etc/apt/keyrings/packages.mozilla.org.asc] https://packages.mozilla.org/apt mozilla main" | tee -a /etc/apt/sources.list.d/mozilla.list > /dev/null \
 && echo $' \n\
Package: * \n\
Pin: origin packages.mozilla.org \n\
Pin-Priority: 1000 \n\
' | tee /etc/apt/preferences.d/mozilla \
 && cat /etc/apt/preferences.d/mozilla \
 && apt-get update \
 && apt-get install -y --no-install-recommends firefox \
 && rm -fr /var/lib/apt/lists/* \
 && curl --proto "=https" -L https://github.com/mozilla/geckodriver/releases/download/v0.30.0/geckodriver-v0.30.0-linux64.tar.gz | tar xz -C /usr/local/bin \
 && apt-get purge -y ca-certificates curl

USER nonroot

# Copy python virtual environment from build layer
COPY --chown=nonroot:nonroot --chmod=544 --from=build /venv /venv

# Using python virtual environment, preload selenium with firefox so that first runtime is faster.
SHELL ["/bin/bash", "-c"]
RUN source /venv/bin/activate && \
    selenium-manager --browser firefox --debug

# Copy source files and essential runtime files
COPY --chown=nonroot:nonroot --chmod=444 selected_polygon.geojson .
COPY --chown=nonroot:nonroot --chmod=644 instructions.json .
COPY --chown=nonroot:nonroot --chmod=544 src/ src/


FROM runtime-base AS backend
# Image build target for backend
# Using separate build targets for each image because the Orbica platform does not allow for modifying entrypoints
# and using multiple dockerfiles was creating increase complexity problems keeping things in sync
EXPOSE 5000

SHELL ["/bin/bash", "-c"]
ENTRYPOINT source /venv/bin/activate && \
           gunicorn --bind 0.0.0.0:5000 src.app:app


FROM runtime-base AS celery_worker
# Image build target for celery_worker

SHELL ["/bin/bash", "-c"]
ENTRYPOINT source /venv/bin/activate && \
           celery -A src.tasks worker -P threads --loglevel=INFO
