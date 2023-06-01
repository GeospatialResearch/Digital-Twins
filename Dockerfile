FROM continuumio/miniconda3 as base

WORKDIR app/


COPY environment.yml .
RUN conda env create -f environment.yml
# Make RUN commands use the new environment:
SHELL ["conda", "run", "-n", "digitaltwin", "/bin/bash", "-c"]

RUN echo "Check GeoFabrics is installed to test environment"
RUN python -c "import geofabrics"

COPY selected_polygon.geojson .
COPY src/ src/

EXPOSE 5000
ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "digitaltwin", "gunicorn", "--bind", "0.0.0.0:5000", "src.app:app"]
