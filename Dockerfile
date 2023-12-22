FROM lparkinson/bg_flood:v0.9

WORKDIR /app

# Install Miniconda
ENV PATH="/root/miniconda3/bin:${PATH}"
ARG PATH="/root/miniconda3/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y git \
                          wget\
    && rm -rf /var/lib/apt/lists/*

RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh \
    && mkdir /root/.conda \
    && bash Miniconda3-latest-Linux-x86_64.sh -b \
    && rm -f Miniconda3-latest-Linux-x86_64.sh
RUN conda --version

COPY environment.yml .
RUN conda env create -f environment.yml
# Make RUN commands use the new environment:
SHELL ["conda", "run", "-n", "digitaltwin", "/bin/bash", "-c"]

RUN echo "Check GeoFabrics is installed to test environment"
RUN python -c "import geofabrics"

COPY selected_polygon.geojson .
COPY instructions.json .
COPY src/ src/

EXPOSE 5000
ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "digitaltwin", "python", "-m", "src.run_all"]
