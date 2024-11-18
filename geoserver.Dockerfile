FROM docker.osgeo.org/geoserver:2.21.2 AS geoserver

# Dockerfile for the geoserver instance of the digital twin, serves geospatial data from files and db.

# Allows nonroot users in other containers to write to shared GEOSERVER_DATA_DIR volume
RUN <<EOF
    addgroup --system nonroot
    adduser --system --group nonroot
    chgrp -R nonroot "$GEOSERVER_DATA_DIR"
    chmod -R g+rwx "$GEOSERVER_DATA_DIR"
EOF

SHELL ["/bin/sh", "-c"]
ENTRYPOINT ["/opt/startup.sh"]
