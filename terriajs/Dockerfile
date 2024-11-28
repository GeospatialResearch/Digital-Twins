# syntax=docker/dockerfile:1.4
FROM lparkinson/otakaro_terria_map:1.6

# Install envsubst dependencies
USER root
RUN <<EOF
    apt-get update
    apt-get install -y --no-install-recommends gettext-base
    # Cleanup image and remove junk
    rm -fr /var/lib/apt/lists/*
EOF
USER node

# Copy Terria.js config
COPY --chown=node:node --chmod=644 client_config.json wwwroot/config.json
COPY --chown=node:node --chmod=644 catalog.json wwwroot/init/catalog.json

COPY --chown=root:root --chmod=755 entrypoint.sh .
SHELL ["/bin/bash", "-c"]
ENTRYPOINT ["/app/entrypoint.sh"]
