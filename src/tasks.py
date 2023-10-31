"""
Runs backend tasks using Celery. Allowing for multiple long-running tasks to complete in the background.
Allows the frontend to send tasks and retrieve status later.
"""
import logging
from typing import List, Tuple

import geopandas as gpd
import pandas as pd
import shapely
import xarray
from celery import Celery, states, result
from newzealidar import process
from pyproj import Transformer

from src.config import get_env_variable
from src.digitaltwin import run, setup_environment
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
    return (add_base_data_to_db.si(selected_polygon_wkt) |
            process_dem.si(selected_polygon_wkt) |
            generate_rainfall_inputs.si(selected_polygon_wkt) |
            generate_tide_inputs.si(selected_polygon_wkt, scenario_options) |
            generate_river_inputs.si(selected_polygon_wkt) |
            run_flood_model.si(selected_polygon_wkt)
            )()


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
    parameters = DEFAULT_MODULES_TO_PARAMETERS[run]
    selected_polygon = wkt_to_gdf(selected_polygon_wkt)
    run.main(selected_polygon, **parameters)


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
    parameters = DEFAULT_MODULES_TO_PARAMETERS[process]
    selected_polygon = wkt_to_gdf(selected_polygon_wkt)
    process.main(selected_polygon, **parameters)


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
def get_distinct_column_values(table_name: str) -> dict:
    engine = setup_environment.get_database()
    column_names = pd.read_sql(
        "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%(table_name)s",
        engine, params={'table_name': 'sea_level_rise'})
    distinct_column_values = {}
    for col_name, in column_names.values:
        if col_name not in ("siteid", "lon", "lat", "region", "geometry"):
            # Can use fstring here because the variables have been sanitised above
            distinct_values = pd.read_sql(f"SELECT DISTINCT {col_name} FROM {table_name} ORDER BY {col_name}", engine)
            if col_name== "measurementname" and table_name=="sea_level_rise":
                distinct_column_values['confidence_level'] = distinct_values['measurementname'].str.extract(
                    r'(low|medium) confidence')[0].unique().tolist()
                # Extract the 'ssp_scenario' information from the 'measurementname' column
                distinct_column_values['ssp_scenario'] = distinct_values['measurementname'].str.extract(r'(\w+-\d\.\d)')[0].unique().tolist()
                # Extract for the presence of '+ VLM' in the 'measurementname' column
                distinct_column_values['add_vlm'] = [True, False]
            else:
                distinct_column_values[col_name] = distinct_values.values.ravel().tolist()

    return distinct_column_values


if __name__ == '__main__':
    # llat = -43.38205648955185
    # llng = 172.6487081332888
    # id = 82
    # get_depth_by_time_at_point(82, llat, llng)
    x = get_distinct_column_values("sea_level_rise")
    print(x)
