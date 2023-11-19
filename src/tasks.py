import geopandas as gpd
import shapely
from celery import Celery, states, result

from src.digitaltwin import retrieve_static_boundaries
from src.dynamic_boundary_conditions import main_rainfall
from src.flood_model import bg_flood_model

from .config import get_env_variable

message_broker_url = f"redis://{get_env_variable('MESSAGE_BROKER_HOST')}:6379/0"

app = Celery("tasks", backend=message_broker_url, broker=message_broker_url)


class OnFailureStateTask(app.Task):
    """Task that switches state to FAILURE if an exception occurs"""

    def on_failure(self, _exc, _task_id, _args, _kwargs, _einfo):
        self.update_state(state=states.FAILURE)


# noinspection PyUnnecessaryBackslash
def create_model_for_area(selected_polygon_wkt: str) -> result.GroupResult:
    """Creates a model for the area using series of chained (sequential) and grouped (parallel) sub-tasks"""
    return (initialise_db_with_region_geometries.si() |
            download_lidar_data.si(selected_polygon_wkt) |
            generate_rainfall_inputs.si(selected_polygon_wkt) |
            run_flood_model.si(selected_polygon_wkt)
            )()


@app.task(base=OnFailureStateTask)
def initialise_db_with_region_geometries():
    retrieve_static_boundaries.main()


@app.task(base=OnFailureStateTask)
def generate_rainfall_inputs(selected_polygon_wkt: str):
    selected_polygon = wkt_to_gdf(selected_polygon_wkt)
    main_rainfall.main(selected_polygon)


@app.task(base=OnFailureStateTask)
def run_flood_model(selected_polygon_wkt: str):
    selected_polygon = wkt_to_gdf(selected_polygon_wkt)
    bg_flood_model.main(selected_polygon)


def wkt_to_gdf(wkt: str) -> gpd.GeoDataFrame:
    selected_polygon = gpd.GeoDataFrame(index=[0], crs="epsg:4326", geometry=[shapely.from_wkt(wkt)])
    return selected_polygon.to_crs(2193)
