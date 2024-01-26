FROM lparkinson/bg_flood:v0.9

WORKDIR /app

# Install firefox browser for use within selenium
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl firefox \
 && rm -fr /var/lib/apt/lists/* \
 && curl -L https://github.com/mozilla/geckodriver/releases/download/v0.30.0/geckodriver-v0.30.0-linux64.tar.gz | tar xz -C /usr/local/bin \
 && apt-get purge -y ca-certificates curl

# Install Miniconda
ENV PATH="/root/miniconda3/bin:${PATH}"
ARG PATH="/root/miniconda3/bin:${PATH}"
RUN apt-get update \
    && apt-get install -y --no-install-recommends git wget ca-certificates \
    && rm -fr /var/lib/apt/lists/* \
    && wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh \
    && mkdir /root/.conda \
    && bash Miniconda3-latest-Linux-x86_64.sh -b \
    && rm -f Miniconda3-latest-Linux-x86_64.sh
RUN conda --version

# Create conda environment
COPY environment.yml .
RUN conda env create -f environment.yml

# Make RUN commands use the new environment:
SHELL ["conda", "run", "-n", "digitaltwin", "/bin/bash", "-c"]

# Test that conda environment worked successfully
RUN echo "Check GeoFabrics is installed to test environment"
RUN python -c "import geofabrics"

# Using conda  environment, preload selenium with firefox so that first runtime is faster.
RUN selenium-manager --browser firefox --debug

# Copy source files and essential runtime files
COPY selected_polygon.geojson .
COPY instructions.json .
COPY src/ src/

EXPOSE 5000
ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "digitaltwin", "gunicorn", "--bind", "0.0.0.0:5000", "src.app:app"]
