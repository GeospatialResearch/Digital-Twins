"""
Runs backend tasks using Celery. Allowing for multiple long-running tasks to complete in the background.
Allows the frontend to send tasks and retrieve status later.
"""
import logging
from typing import Dict, Union, Optional

import sqlalchemy.exc
from celery import signals
from celery.worker.consumer import Consumer
import geopandas as gpd

from src.digitaltwin import retrieve_from_instructions
from src.digitaltwin.utils import setup_logging
from src.tasks import add_base_data_to_db, app, OnFailureStateTask, wkt_to_gdf
from otakaro import initialise_db_with_files
from otakaro.environmental.water_quality import surface_water_sites
from otakaro.pollution_model import run_medusa_2
from otakaro.run_all import DEFAULT_MODULES_TO_PARAMETERS

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
        sender.app.send_task("otakaro.tasks.add_files_data_to_db", connection=conn)


@app.task(base=OnFailureStateTask)
def add_files_data_to_db() -> None:
    """Read roof surface polygons data then store them into database."""
    parameters = DEFAULT_MODULES_TO_PARAMETERS[initialise_db_with_files]
    initialise_db_with_files.main(**parameters)


@app.task(base=OnFailureStateTask)
def run_medusa_model(selected_polygon_wkt: str,
                     antecedent_dry_days: float,
                     average_rain_intensity: float,
                     event_duration: float,
                     rainfall_ph: float = 6.5) -> int:
    """
    Create a model for the area using series of chained (sequential) sub-tasks.

    Parameters
    ----------
    selected_polygon_wkt : gpd.GeoDataFrame
        A wkt encoding string representing the area of interest, in epsg:4326.
    antecedent_dry_days: float
        The number of dry days between rainfall events.
    average_rain_intensity: float
        The intensity of the rainfall event in mm/h.
    event_duration: float
        The number of hours of the rainfall event.
    rainfall_ph: float
        The pH level of the rainfall, a measure of acidity.

    Returns
    -------
    int
       The scenario id of the new medusa scenario produced
    """
    # Convert wkt string into a GeoDataFrame
    selected_polygon = wkt_to_gdf(selected_polygon_wkt)

    # Initialise base data
    base_data_parameters = DEFAULT_MODULES_TO_PARAMETERS[retrieve_from_instructions]
    add_base_data_to_db.delay(selected_polygon, base_data_parameters).get()

    # Read log level from default parameters
    log_level = DEFAULT_MODULES_TO_PARAMETERS[run_medusa_2]["log_level"]
    # Run Medusa model
    return run_medusa_2.main(selected_polygon,
                             log_level,
                             antecedent_dry_days,
                             average_rain_intensity,
                             event_duration,
                             rainfall_ph)


@app.task(base=OnFailureStateTask)
def retrieve_medusa_input_parameters(scenario_id: int) -> Optional[Dict[str, Union[str, float]]]:
    """
    Retrieve input parameters for the current scenario id.

    Parameters
    ----------
    scenario_id: int
        The scenario ID of the pollution model run


    Returns
    -------
    Dict[src, Union[str, float]]
        A dictionary contain information from Rainfall MEDUSA 2.0 database or None if scenario does not exist.
    """
    # Get rainfall information
    medusa_rainfall_event = run_medusa_2.retrieve_input_parameters(scenario_id)

    # Return a dictionary format of these parameters or None if no ID found
    if medusa_rainfall_event is None:
        return None

    return dict(medusa_rainfall_event)


@app.task(base=OnFailureStateTask)
def refresh_surface_water_sites() -> None:
    """
    Fetch surface water site data from ECAN and store it in the database.
    Needs to be run periodically so that the surface water site data is up to date.
    """
    surface_water_sites.refresh_surface_water_sites()
