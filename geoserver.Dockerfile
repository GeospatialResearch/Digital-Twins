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

# Dockerfile for setting up geoserver instance
FROM docker.osgeo.org/geoserver:3.0.x AS geoserver

# Dockerfile for the geoserver instance of the digital twin, serves geospatial data from files and db.

# Install extensions for serving NetCDF data
ENV INSTALL_EXTENSIONS="true"
ENV STABLE_EXTENSIONS="netcdf"
ENV COMMUNITY_EXTENSIONS="ncwms,graticule"
RUN /opt/install-extensions.sh

# Allows nonroot users in other containers to write to shared GEOSERVER_DATA_DIR volume
RUN <<EOF
    set -ex
    addgroup --system nonroot
    adduser --system --group nonroot
    chgrp -R nonroot "$GEOSERVER_DATA_DIR"
    chmod -R g+rwx "$GEOSERVER_DATA_DIR"
    cd "$GEOSERVER_DATA_DIR"

    GRATICULE_DIR="workspaces/static_files/Graticule_15"
    mkdir -p $GRATICULE_DIR
    chgrp -R nonroot $GRATICULE_DIR
    chmod -R g+rwx $GRATICULE_DIR
EOF

SHELL ["/bin/sh", "-c"]
ENTRYPOINT ["/opt/startup.sh"]
