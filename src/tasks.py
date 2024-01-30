"""
Runs backend tasks using Celery. Allowing for multiple long-running tasks to complete in the background.
Allows the frontend to send tasks and retrieve status later.
"""
import json
import logging
from typing import List, Tuple

import geopandas as gpd
import newzealidar
import shapely
import xarray
from celery import Celery, states, result
from pyproj import Transformer

from src.config import get_env_variable
from src.digitaltwin import retrieve_static_boundaries, setup_environment, tables
from src.digitaltwin.utils import setup_logging
from src.dynamic_boundary_conditions.rainfall import main_rainfall
from src.dynamic_boundary_conditions.river import main_river
from src.dynamic_boundary_conditions.tide import main_tide_slr
from src.flood_model import bg_flood_model
from src.run_all import DEFAULT_MODULES_TO_PARAMETERS

# Setup celery backend task management
message_broker_url = f"redis://{get_env_variable('MESSAGE_BROKER_HOST')}:6379/0"
app = Celery("tasks", backend=message_broker_url, broker=message_broker_url)

setup_logging()
log = logging.getLogger(__name__)


class OnFailureStateTask(app.Task):
    """Task that switches state to FAILURE if an exception occurs"""

    def on_failure(self, _exc, _task_id, _args, _kwargs, _einfo):
        self.update_state(state=states.FAILURE)


# noinspection PyUnnecessaryBackslash
def create_model_for_area(selected_polygon_wkt: str, scenario_options: dict) -> result.GroupResult:
    """
    Creates a model for the area using series of chained (sequential) and grouped (parallel) sub-tasks.

    Parameters
    ----------
    selected_polygon_wkt : str
        The polygon defining the selected area to run the model for. Defined in WKT form.

    Returns
    -------
    result.GroupResult
        The task result for the long-running group of tasks. The task ID represents the final task in the group.
    """
    return (
            ensure_lidar_datasets_initialised.si() |
            add_base_data_to_db.si(selected_polygon_wkt) |
            process_dem.si(selected_polygon_wkt) |
            generate_rainfall_inputs.si(selected_polygon_wkt) |
            generate_river_inputs.si(selected_polygon_wkt) |
            run_flood_model.si(selected_polygon_wkt)
    )()


@app.task(base=OnFailureStateTask)
def ensure_lidar_datasets_initialised() -> None:
    """
    Task checks if LiDAR datasets table is initialised.
    This table holds URLs to data sources for LiDAR.
    If it is not initialised, then it initialises it by web-scraping OpenTopography which takes a long time.

    Returns
    -------
    None
        This task does not return anything
    """
    # Connect to database
    engine = setup_environment.get_connection_from_profile()
    # Check if datasets table initialised
    if not tables.check_table_exists(engine, "dataset"):
        # If it is not initialised, then initialise it
        newzealidar.datasets.main()
    # Check that datasets_mapping is in the instructions.json file
    with open("instructions.json", "r") as file:
        # Load content from the file
        instructions = json.load(file)["instructions"]
    dataset_mapping = instructions.get("dataset_mapping")
    # If the dataset_mapping does not exist on the instruction file then read it from the database
    if dataset_mapping is None:
        # Add dataset_mapping to instructions file, reading from database
        newzealidar.utils.map_dataset_name(engine, instructions_file)


@app.task(base=OnFailureStateTask)
def add_base_data_to_db(selected_polygon_wkt: str) -> None:
    """
    Task to ensure static base data for the given area is added to the database

    Parameters
    ----------
    selected_polygon_wkt : str
        The polygon defining the selected area to add base data for. Defined in WKT form.

    Returns
    -------
    None
        This task does not return anything
    """
    parameters = DEFAULT_MODULES_TO_PARAMETERS[retrieve_static_boundaries]
    selected_polygon = wkt_to_gdf(selected_polygon_wkt)
    retrieve_static_boundaries.main(selected_polygon, **parameters)


@app.task(base=OnFailureStateTask)
def process_dem(selected_polygon_wkt: str):
    """
    Task to ensure hydrologically-conditioned DEM is processed for the given area and added to the database.

    Parameters
    ----------
    selected_polygon_wkt : str
        The polygon defining the selected area to process the DEM for. Defined in WKT form.

    Returns
    -------
    None
        This task does not return anything
    """
    parameters = DEFAULT_MODULES_TO_PARAMETERS[newzealidar.process]
    selected_polygon = wkt_to_gdf(selected_polygon_wkt)
    newzealidar.process.main(selected_polygon, **parameters)


@app.task(base=OnFailureStateTask)
def generate_rainfall_inputs(selected_polygon_wkt: str):
    """
    Task to ensure rainfall input data for the given area is added to the database and model input files are created.

    Parameters
    ----------
    selected_polygon_wkt : str
        The polygon defining the selected area to add rainfall data for. Defined in WKT form.

    Returns
    -------
    None
        This task does not return anything
    """
    parameters = DEFAULT_MODULES_TO_PARAMETERS[main_rainfall]
    selected_polygon = wkt_to_gdf(selected_polygon_wkt)
    main_rainfall.main(selected_polygon, **parameters)


@app.task(base=OnFailureStateTask)
def generate_tide_inputs(selected_polygon_wkt: str, scenario_options: dict):
    """
    Task to ensure tide input data for the given area is added to the database and model input files are created.

    Parameters
    ----------
    selected_polygon_wkt : str
        The polygon defining the selected area to add tide data for. Defined in WKT form.

    Returns
    -------
    None
        This task does not return anything
    """
    parameters = DEFAULT_MODULES_TO_PARAMETERS[main_tide_slr]
    parameters["proj_year"] = scenario_options["Projected Year"]
    parameters["add_vlm"] = scenario_options["Add Vertical Land Movement"]
    parameters["confidence_level"] = scenario_options["Confidence Level"]
    selected_polygon = wkt_to_gdf(selected_polygon_wkt)
    main_tide_slr.main(selected_polygon, **parameters)


@app.task(base=OnFailureStateTask)
def generate_river_inputs(selected_polygon_wkt: str):
    """
    Task to ensure river input data for the given area is added to the database and model input files are created.

    Parameters
    ----------
    selected_polygon_wkt : str
        The polygon defining the selected area to add river data for. Defined in WKT form.

    Returns
    -------
    None
        This task does not return anything
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
    Takes a long time to run but needs to be run periodically so that the datasets are up to date

    Returns
    -------
    None
        This task does not return anything
    """
    newzealidar.datasets.main()


def wkt_to_gdf(wkt: str) -> gpd.GeoDataFrame:
    """
    Transforms a WKT string polygon into a GeoDataFrame

    Parameters
    ----------
    wkt : str
        The WKT form of the polygon to be transformed. In WGS84 CRS (epsg:4326).

    Returns
    -------
    gpd.GeoDataFrame
        The GeoDataFrame form of the polygon after being transformed.
    """
    selected_polygon = gpd.GeoDataFrame(index=[0], crs="epsg:4326", geometry=[shapely.from_wkt(wkt)])

    # Convert the polygon to 2193 crs, and recalculate the bounds to ensure it is a rectangle.
    bbox_2193 = selected_polygon.to_crs(2193).bounds
    xmin, ymin, xmax, ymax = (bbox_2193[bound_variable][0] for bound_variable in ("minx", "miny", "maxx", "maxy"))
    selected_as_rectangle_2193 = gpd.GeoDataFrame(index=[0], crs="epsg:2193",
                                                  geometry=[shapely.box(xmin, ymin, xmax, ymax)])

    return selected_as_rectangle_2193


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
        Serialized posix-style str version of the filepath
    """
    return bg_flood_model.model_output_from_db_by_id(model_id).as_posix()


@app.task(base=OnFailureStateTask)
def get_depth_by_time_at_point(model_id: int, lat: float, lng: float) -> Tuple[List[float], List[float]]:
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
    Tuple[List[float], List[float]]
        Tuple of depths list and times list for the pixel in the output nearest to the point.
    """
    model_file_path = bg_flood_model.model_output_from_db_by_id(model_id).as_posix()
    with xarray.open_dataset(model_file_path) as ds:
        transformer = Transformer.from_crs(4326, 2193)
        y, x = transformer.transform(lat, lng)
        da = ds["hmax_P0"].sel(x=x, y=y, method="nearest")

    depths = da.values.tolist()
    times = da.coords['time'].values.tolist()
    return depths, times


@app.task(base=OnFailureStateTask)
def get_model_extents_bbox(model_id: int) -> str:
    """
    Task to find the bounding box of a given model output

    Parameters
    ----------
    model_id : int
        The database id of the model output to query.

    Returns
    -------
    str:
        The bounding box in '[x1],[y1],[x2],[y2]' format
    """
    extents = bg_flood_model.model_extents_from_db_by_id(model_id).geometry[0]
    # Retrieve a tuple of the corners of the extents
    bbox_corners = extents.bounds
    # Convert the tuple into a string in [x1],[y1],[x2],[y2]
    return ",".join(map(str, bbox_corners))
