import time

from celery import Celery, states, result

from .config import get_env_variable

message_broker_url = f"redis://{get_env_variable('MESSAGE_BROKER_HOST')}:6379/0"

app = Celery("tasks", backend=message_broker_url, broker=message_broker_url)


class OnFailureStateTask(app.Task):
    """Task that switches state to FAILURE if an exception occurs"""

    def on_failure(self, _exc, _task_id, _args, _kwargs, _einfo):
        self.update_state(state=states.FAILURE)


# noinspection PyUnnecessaryBackslash
def create_model_for_area(bbox_wkt: str) -> result.GroupResult:
    """Creates a model for the area using series of chained (sequential) and grouped (parallel) sub-tasks"""
    return (initialise_db_with_region_geometries.si(bbox_wkt) |
            download_lidar_data.si(bbox_wkt) |
            generate_rainfall_inputs.si(bbox_wkt) |
            run_flood_model.si(bbox_wkt)
            )()


@app.task(base=OnFailureStateTask)
def initialise_db_with_region_geometries(bbox_wkt: str):
    # run.main()
    time.sleep(5)


@app.task(base=OnFailureStateTask)
def download_lidar_data(bbox_wkt: str):
    # lidar_metadata_in_db.main()
    time.sleep(5)


@app.task(base=OnFailureStateTask)
def generate_rainfall_inputs(bbox_wkt: str):
    # main_rainfall.main()
    time.sleep(5)


@app.task(base=OnFailureStateTask)
def run_flood_model(bbox_wkt: str):
    # bg_flood_model.main()
    time.sleep(5)
