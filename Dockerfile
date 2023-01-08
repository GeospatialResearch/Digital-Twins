FROM continuumio/miniconda3 as base

WORKDIR app/


COPY environment.yml .
RUN conda env create -f environment.yml
# Make RUN commands use the new environment:
SHELL ["conda", "run", "-n", "digitaltwin", "/bin/bash", "-c"]

RUN echo "Check GeoFabrics is installed to test environment"
RUN python -c "import geofabrics"

COPY src/ src/
ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "digitaltwin", "python", "-m", "src.run_all"]
