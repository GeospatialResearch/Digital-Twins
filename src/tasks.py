from celery import Celery, states, group

from .config import get_env_variable
from .digitaltwin import run
from .dynamic_boundary_conditions import main_rainfall
from .flood_model import bg_flood_model
from .lidar import lidar_metadata_in_db

message_broker_url = f"redis://{get_env_variable('MESSAGE_BROKER_HOST')}:6379/0"

app = Celery("tasks", backend=message_broker_url, broker=message_broker_url)


class OnFailureStateTask(app.Task):
    """Task that switches state to FAILURE if an exception occurs"""

    def on_failure(self, _exc, _task_id, _args, _kwargs, _einfo):
        self.update_state(state=states.FAILURE)


# noinspection PyUnnecessaryBackslash
@app.task(base=OnFailureStateTask)
def create_model_for_area():
    """Creates a model for the area using series of chained (sequential) and grouped (parallel) sub-tasks"""
    return (
            initialise_db_with_region_geometries.si() | \
            group(
                download_lidar_data.si() | \
                generate_rainfall_inputs.si()
            ) | \
            run_flood_model.si()
    )()


@app.task(base=OnFailureStateTask, ignore_result=True)
def initialise_db_with_region_geometries():
    run.main()


@app.task(base=OnFailureStateTask, ignore_result=True)
def download_lidar_data():
    lidar_metadata_in_db.main()


@app.task(base=OnFailureStateTask, ignore_result=True)
def generate_rainfall_inputs():
    main_rainfall.main()


@app.task(base=OnFailureStateTask, ignore_result=True)
def run_flood_model():
    bg_flood_model.main()
