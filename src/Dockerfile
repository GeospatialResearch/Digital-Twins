# Copyright © 2021-2025 Geospatial Research Institute Toi Hangarau
# LICENSE: https://github.com/GeospatialResearch/Digital-Twins/blob/master/LICENSE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Main Dockerfile for setting up services defined in docker-compose.yml.

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

RUN <<EOF
    # Export conda environment
    echo "Check GeoFabrics is installed to test environment"
    python -c "import geofabrics"
    echo "Packaging conda environment - digitaltwin"
    # Pack conda environment to be shared to runtime image
    # Pack current conda environment to temporary tarball
    conda-pack --ignore-missing-files -n digitaltwin -o /tmp/env.tar
    mkdir /venv
    cd /venv
    # Extract tarball to /venv
    tar xf /tmp/env.tar
    rm /tmp/env.tar
    # Cleanup prefixes and create activation scripts
    /venv/bin/conda-unpack
EOF

FROM lparkinson/bg_flood:v0.9 AS runtime
# BG_Flood stage for running the digital twin. Reduces image size significantly if we use a multi-stage build
WORKDIR /app

USER root

# Install health-checker tool that allows us to run commands when checking root endpoint to check if service is available
ADD --chmod=555 https://github.com/gruntwork-io/health-checker/releases/download/v0.0.8/health-checker_linux_amd64 \
 /usr/local/bin/health-checker

RUN <<EOF
    # Install dependencies
    apt-get update
    apt-get install -y --no-install-recommends \
      acl \
      ca-certificates \
      curl \
      gettext-base
    # Cleanup image and remove junk
    rm -fr /var/lib/apt/lists/*
    # Remove unused packages. Keep curl for health checking in docker-compose
    apt-get purge -y ca-certificates

    # Create stored data dir inside image, in case it does not get mounted (such as when deploying on AWS)
    mkdir /stored_data
    # Allow permissions for nonroot user
    setfacl -R -d -m u:nonroot:rwx /stored_data
    setfacl -R -m u:nonroot:rwx /stored_data
    # Create geoserver shared directory
    mkdir /stored_data/geoserver

    # Create PyWPS required logging and output directories
    for NEW_DIRECTORY in "outputs" "workdir" "logs"
    do
        mkdir "$NEW_DIRECTORY"
        setfacl -R -d -m u:nonroot:rwx "$NEW_DIRECTORY"
        setfacl -R -m u:nonroot:rwx "$NEW_DIRECTORY"
    done
EOF

# Copy python virtual environment from build layer
COPY --chown=root:root --chmod=555 --from=build /venv /venv

# Copy source files and essential runtime files
COPY --chown=root:root --chmod=444 selected_polygon.geojson .
COPY --chown=nonroot:nonroot --chmod=644 instructions.json .
COPY --chown=root:root --chmod=555 src src/
COPY --chown=root:root --chmod=555 floodresilience floodresilience/
COPY --chown=nonroot:nonroot --chmod=644 src/pywps.cfg src/

USER nonroot
