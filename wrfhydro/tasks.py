"""
Runs backend tasks using Celery. Allowing for multiple long-running tasks to complete in the background.
Allows the frontend to send tasks and retrieve status later.
"""
import logging

from celery import result, signals
from celery.worker.consumer import Consumer
import geopandas as gpd

from src.digitaltwin import retrieve_from_instructions
from src.digitaltwin.utils import setup_logging
from src.tasks import add_base_data_to_db, app, OnFailureStateTask, wkt_to_gdf  # pylint: disable=cyclic-import
from wrfhydro.forcing_data import read_forcing_data
from wrfhydro.land_surface_model import create_land_surface_model
from wrfhydro.scenario import run_wrf_hydro_scenario
from wrfhydro.run_all import DEFAULT_MODULES_TO_PARAMETERS

setup_logging()
log = logging.getLogger(__name__)


@signals.worker_ready.connect
def on_startup(sender: Consumer, **_kwargs: None) -> None:  # pylint: disable=missing-param-doc
    """
    Initialise database, runs when Celery instance is ready.

    Parameters
    ----------
    sender : Consumer
        The Celery worker node instance
    """
    with sender.app.connection() as conn:
        # Gather area of interest from file.
        aoi_wkt = gpd.read_file("selected_polygon.geojson").to_crs(4326).geometry[0].wkt
        # Send a task to initialise this area of interest.
        base_data_parameters = DEFAULT_MODULES_TO_PARAMETERS[retrieve_from_instructions]
        sender.app.send_task("src.tasks.add_base_data_to_db", args=[aoi_wkt, base_data_parameters], connection=conn)


def create_scenario_for_area(selected_polygon_wkt: str) -> result.GroupResult:
    """
    Create a model for the area using series of chained (sequential) sub-tasks.

    Parameters
    ----------
    selected_polygon_wkt : str
        The polygon defining the selected area to run the model for. Defined in WKT form.

    Returns
    -------
    result.GroupResult
        The task result for the long-running group of tasks. The task ID represents the final task in the group.
    """
    base_data_parameters = DEFAULT_MODULES_TO_PARAMETERS[retrieve_from_instructions]
    return (
        add_base_data_to_db.si(selected_polygon_wkt, base_data_parameters) |
        create_land_surface_model_task.si(selected_polygon_wkt) |
        read_forcing_data_task.si(selected_polygon_wkt) |
        run_wrf_scenario_task.si(selected_polygon_wkt)
    )()


@app.task(base=OnFailureStateTask)
def create_land_surface_model_task(selected_polygon_wkt: str) -> None:
    """
    Task to ensure rainfall input data for the given area is added to the database and model input files are created.

    Parameters
    ----------
    selected_polygon_wkt : str
        The polygon defining the selected area to add rainfall data for. Defined in WKT form.
    """
    parameters = DEFAULT_MODULES_TO_PARAMETERS[create_land_surface_model]
    selected_polygon = wkt_to_gdf(selected_polygon_wkt)
    create_land_surface_model.main(selected_polygon, **parameters)


@app.task(base=OnFailureStateTask)
def read_forcing_data_task(selected_polygon_wkt: str) -> None:
    """
    Task to ensure meteorological forcing data is processed for the given area and added to the database.

    Parameters
    ----------
    selected_polygon_wkt : str
        The polygon defining the selected area to process the forcing data for. Defined in WKT form.
    """
    parameters = DEFAULT_MODULES_TO_PARAMETERS[read_forcing_data]
    selected_polygon = wkt_to_gdf(selected_polygon_wkt)
    read_forcing_data.main(selected_polygon, **parameters)


@app.task(base=OnFailureStateTask)
def run_wrf_scenario_task(selected_polygon_wkt: str) -> None:
    """
    Task to run a WRF Hydro scenario for a given area.

    Parameters
    ----------
    selected_polygon_wkt : str
        The polygon defining the selected area to run a wrf_hydro scenario for. Defined in WKT form.
    """
    parameters = DEFAULT_MODULES_TO_PARAMETERS[run_wrf_hydro_scenario]
    selected_polygon = wkt_to_gdf(selected_polygon_wkt)
    run_wrf_hydro_scenario.main(selected_polygon, **parameters)
