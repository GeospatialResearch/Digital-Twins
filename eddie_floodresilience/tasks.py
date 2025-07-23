"""
Runs backend tasks using Celery. Allowing for multiple long-running tasks to complete in the background.
Allows the frontend to send tasks and retrieve status later.
"""
import logging
from typing import Dict, List, NamedTuple, Union

from celery import result, signals
from celery.worker.consumer import Consumer
import geopandas as gpd
from pyproj import Transformer
import xarray

from src.digitaltwin import setup_environment, retrieve_from_instructions
from src.digitaltwin.utils import setup_logging
from src.tasks import add_base_data_to_db, app, OnFailureStateTask, wkt_to_gdf  # pylint: disable=cyclic-import
from eddie_floodresilience.dynamic_boundary_conditions.rainfall import main_rainfall
from eddie_floodresilience.dynamic_boundary_conditions.river import main_river
from eddie_floodresilience.dynamic_boundary_conditions.tide import main_tide_slr
from eddie_floodresilience.flood_model import bg_flood_model, process_hydro_dem
from eddie_floodresilience.run_all import DEFAULT_MODULES_TO_PARAMETERS

setup_logging()
log = logging.getLogger(__name__)


class DepthTimePlot(NamedTuple):
    """
    Represents the depths over time for a particular pixel location in a raster.
    Uses tuples and lists instead of Arrays or Dataframes because it needs to be easily serializable when communicating
    over message_broker.

    Attributes
    ----------
    depths : List[float]
        A list of all of the depths in m for the pixel. Parallels the times list
    times : List[float]
        A list of all of the times in s for the pixel. Parallels the depts list
    """

    depths: List[float]
    times: List[float]


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
        # Send a task to ensure lidar datasets are evaluated.
        sender.app.send_task("eddie_floodresilience.tasks.ensure_lidar_datasets_initialised")


def create_model_for_area(selected_polygon_wkt: str, scenario_options: dict) -> result.GroupResult:
    """
    Create a model for the area using series of chained (sequential) sub-tasks.

    Parameters
    ----------
    selected_polygon_wkt : str
        The polygon defining the selected area to run the model for. Defined in WKT form.
    scenario_options: dict
        Options for scenario modelling inputs.

    Returns
    -------
    result.GroupResult
        The task result for the long-running group of tasks. The task ID represents the final task in the group.
    """
    base_data_parameters = DEFAULT_MODULES_TO_PARAMETERS[retrieve_from_instructions]
    return (
        add_base_data_to_db.si(selected_polygon_wkt, base_data_parameters) |
        process_dem.si(selected_polygon_wkt) |
        generate_rainfall_inputs.si(selected_polygon_wkt) |
        generate_tide_inputs.si(selected_polygon_wkt, scenario_options) |
        generate_river_inputs.si(selected_polygon_wkt) |
        run_flood_model.si(selected_polygon_wkt)
    )()


@app.task(base=OnFailureStateTask)
def process_dem(selected_polygon_wkt: str) -> None:
    """
    Task to ensure hydrologically-conditioned DEM is processed for the given area and added to the database.

    Parameters
    ----------
    selected_polygon_wkt : str
        The polygon defining the selected area to process the DEM for. Defined in WKT form.
    """
    parameters = DEFAULT_MODULES_TO_PARAMETERS[process_hydro_dem]
    selected_polygon = wkt_to_gdf(selected_polygon_wkt)
    process_hydro_dem.main(selected_polygon, **parameters)


@app.task(base=OnFailureStateTask)
def generate_rainfall_inputs(selected_polygon_wkt: str) -> None:
    """
    Task to ensure rainfall input data for the given area is added to the database and model input files are created.

    Parameters
    ----------
    selected_polygon_wkt : str
        The polygon defining the selected area to add rainfall data for. Defined in WKT form.
    """
    parameters = DEFAULT_MODULES_TO_PARAMETERS[main_rainfall]
    selected_polygon = wkt_to_gdf(selected_polygon_wkt)
    main_rainfall.main(selected_polygon, **parameters)


@app.task(base=OnFailureStateTask)
def generate_tide_inputs(selected_polygon_wkt: str, scenario_options: dict) -> None:
    """
    Task to ensure tide input data for the given area is added to the database and model input files are created.

    Parameters
    ----------
    selected_polygon_wkt : str
        The polygon defining the selected area to add tide data for. Defined in WKT form.
    scenario_options: dict
        Options for scenario modelling inputs.
    """
    parameters = DEFAULT_MODULES_TO_PARAMETERS[main_tide_slr] | scenario_options
    selected_polygon = wkt_to_gdf(selected_polygon_wkt)
    main_tide_slr.main(selected_polygon, **parameters)


@app.task(base=OnFailureStateTask)
def generate_river_inputs(selected_polygon_wkt: str) -> None:
    """
    Task to ensure river input data for the given area is added to the database and model input files are created.

    Parameters
    ----------
    selected_polygon_wkt : str
        The polygon defining the selected area to add river data for. Defined in WKT form.
    """
    parameters = DEFAULT_MODULES_TO_PARAMETERS[main_river]
    selected_polygon = wkt_to_gdf(selected_polygon_wkt)
    main_river.main(selected_polygon, **parameters)


@app.task(base=OnFailureStateTask)
def run_flood_model(selected_polygon_wkt: str) -> int:
    """
    Task to run flood model using input data from previous tasks.

    Parameters
    ----------
    selected_polygon_wkt : str
        The polygon defining the selected area to run the flood model for. Defined in WKT form.

    Returns
    -------
    int
        The database ID of the flood model that has been run.
    """
    parameters = DEFAULT_MODULES_TO_PARAMETERS[bg_flood_model]
    selected_polygon = wkt_to_gdf(selected_polygon_wkt)
    flood_model_id = bg_flood_model.main(selected_polygon, **parameters)
    return flood_model_id


@app.task(base=OnFailureStateTask)
def refresh_lidar_datasets() -> None:
    """
    Web-scrapes OpenTopography metadata to create the datasets table containing links to LiDAR data sources.
    Takes a long time to run but needs to be run periodically so that the datasets are up to date.
    """
    process_hydro_dem.refresh_lidar_datasets()


@app.task(base=OnFailureStateTask)
def ensure_lidar_datasets_initialised() -> None:
    """
    Check if LiDAR datasets table is initialised.
    This table holds URLs to data sources for LiDAR.
    If it is not initialised, then it initialises it by web-scraping OpenTopography which takes a long time.
    """
    process_hydro_dem.ensure_lidar_datasets_initialised()


@app.task(base=OnFailureStateTask)
def get_model_output_filepath_from_model_id(model_id: int) -> str:
    """
    Task to query the database and find the filepath for the model output for the model_id.

    Parameters
    ----------
    model_id : int
        The database id of the model output to query.

    Returns
    -------
    str
        Serialized posix-style str version of the filepath.
    """
    engine = setup_environment.get_connection_from_profile()
    return bg_flood_model.model_output_from_db_by_id(engine, model_id).as_posix()


@app.task(base=OnFailureStateTask)
def get_depth_by_time_at_point(model_id: int, lat: float, lng: float) -> DepthTimePlot:
    """
    Task to query a point in a flood model output and return the list of depths and times.

    Parameters
    ----------
    model_id : int
        The database id of the model output to query.
    lat : float
        The latitude of the point to query.
    lng : float
        The longitude of the point to query.


    Returns
    -------
    DepthTimePlot
        Tuple of depths list and times list for the pixel in the output nearest to the point.
    """
    engine = setup_environment.get_connection_from_profile()
    model_file_path = bg_flood_model.model_output_from_db_by_id(engine, model_id).as_posix()
    with xarray.open_dataset(model_file_path) as ds:
        transformer = Transformer.from_crs(4326, 2193)
        y, x = transformer.transform(lat, lng)
        da = ds["hmax_P0"].sel(xx_P0=x, yy_P0=y, method="nearest")

    depths = da.values.tolist()
    times = da.coords['time'].values.tolist()
    return DepthTimePlot(depths, times)


@app.task(base=OnFailureStateTask)
def get_model_extents_bbox(model_id: int) -> str:
    """
    Task to find the bounding box of a given model output.

    Parameters
    ----------
    model_id : int
        The database id of the model output to query.

    Returns
    -------
    str
        The bounding box in 'x1,y1,x2,y2' format.
    """
    engine = setup_environment.get_connection_from_profile()
    extents = bg_flood_model.model_extents_from_db_by_id(engine, model_id).geometry[0]
    # Retrieve a tuple of the corners of the extents
    bbox_corners = extents.bounds
    # Convert the tuple into a string in x1,y1,x2,y2 form
    return ",".join(map(str, bbox_corners))


@app.task(base=OnFailureStateTask)
def get_valid_parameters_based_on_confidence_level() -> Dict[str, Dict[str, Union[str, int]]]:
    """
    Task to get information on valid tide and sea-level-rise parameters based on the valid values in the database.
    These parameters are mostly dependent on the "confidence_level" parameter, so that is the key in the returned dict.

    Returns
    -------
    Dict[str, Dict[str, Union[str, int]]]
        Dictionary with confidence_level as the key, and 2nd level dict with allowed values for dependent values.
    """
    return main_tide_slr.get_valid_parameters_based_on_confidence_level()


@app.task(base=OnFailureStateTask)
def validate_slr_parameters(
    scenario_options: Dict[str, Union[str, float, int, bool]]
) -> main_tide_slr.ValidationResult:
    """
    Task to validate each of the sea-level-rise parameters.

    Parameters
    ----------
    scenario_options : Dict[str, Union[str, float, int, bool]]
        Options for scenario modelling inputs, coming from JSON body.

    Returns
    -------
    main_tide_slr.ValidationResult
        Result of the validation, with validation failure reason if applicable
    """
    return main_tide_slr.validate_slr_parameters(
        scenario_options["projectedYear"],
        scenario_options["confidenceLevel"],
        scenario_options["sspScenario"],
        scenario_options["addVerticalLandMovement"],
        scenario_options["percentile"],
    )
