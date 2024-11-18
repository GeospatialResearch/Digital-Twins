FROM ghcr.io/terriajs/terriamap:0.2.1

# Install envsubst dependencies
USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends gettext-base \
# Cleanup image and remove junk
 && rm -fr /var/lib/apt/lists/* \
USER node

# Copy Terria.js config
COPY client_config.json wwwroot/config.json
COPY catalog.json wwwroot/init/catalog.json

COPY entrypoint.sh .
SHELL ["/bin/bash", "-c"]
ENTRYPOINT ["/app/entrypoint.sh"]
