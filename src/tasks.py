import logging

import geopandas as gpd
import shapely
from celery import Celery, states, result
from newzealidar import process

from src.digitaltwin import run
from src.digitaltwin.utils import setup_logging
from src.dynamic_boundary_conditions import main_rainfall, main_river, main_tide_slr
from src.flood_model import bg_flood_model
from .config import get_env_variable

message_broker_url = f"redis://{get_env_variable('MESSAGE_BROKER_HOST')}:6379/0"

app = Celery("tasks", backend=message_broker_url, broker=message_broker_url)

setup_logging()
log = logging.getLogger(__name__)


class OnFailureStateTask(app.Task):
    """Task that switches state to FAILURE if an exception occurs"""

    def on_failure(self, _exc, _task_id, _args, _kwargs, _einfo):
        self.update_state(state=states.FAILURE)


# noinspection PyUnnecessaryBackslash
def create_model_for_area(selected_polygon_wkt: str) -> result.GroupResult:
    """Creates a model for the area using series of chained (sequential) and grouped (parallel) sub-tasks"""
    return (add_base_data_to_db.si(selected_polygon_wkt) |
            process_dem.si(selected_polygon_wkt) |
            generate_rainfall_inputs.si(selected_polygon_wkt) |
            generate_tide_inputs.si(selected_polygon_wkt) |
            generate_river_inputs.si(selected_polygon_wkt) |
            run_flood_model.si(selected_polygon_wkt)
            )()


@app.task(base=OnFailureStateTask)
def add_base_data_to_db(selected_polygon_wkt: str):
    selected_polygon = wkt_to_gdf(selected_polygon_wkt)
    run.main(selected_polygon)


@app.task(base=OnFailureStateTask)
def process_dem(selected_polygon_wkt: str):
    selected_polygon = wkt_to_gdf(selected_polygon_wkt)
    process.main(selected_polygon)


@app.task(base=OnFailureStateTask)
def generate_rainfall_inputs(selected_polygon_wkt: str):
    selected_polygon = wkt_to_gdf(selected_polygon_wkt)
    main_rainfall.main(selected_polygon)


@app.task(base=OnFailureStateTask)
def generate_tide_inputs(selected_polygon_wkt: str):
    selected_polygon = wkt_to_gdf(selected_polygon_wkt)
    main_tide_slr.main(selected_polygon)


@app.task(base=OnFailureStateTask)
def generate_river_inputs(selected_polygon_wkt: str):
    selected_polygon = wkt_to_gdf(selected_polygon_wkt)
    main_river.main(selected_polygon)


@app.task(base=OnFailureStateTask)
def run_flood_model(selected_polygon_wkt: str):
    selected_polygon = wkt_to_gdf(selected_polygon_wkt)
    flood_model_id = bg_flood_model.main(selected_polygon)
    return flood_model_id


def wkt_to_gdf(wkt: str) -> gpd.GeoDataFrame:
    selected_polygon = gpd.GeoDataFrame(index=[0], crs="epsg:4326", geometry=[shapely.from_wkt(wkt)])
    return selected_polygon.to_crs(2193)
