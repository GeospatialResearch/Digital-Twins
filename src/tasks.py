from celery import Celery, states

from .digitaltwin import run

message_broker_url = "redis://message_broker:6379/0"

app = Celery("tasks", backend=message_broker_url, broker=message_broker_url)


class OnFailureStateTask(app.Task):
    """Task that switches state to FAILURE if an exception occurs"""
    def on_failure(self, _exc, _task_id, _args, _kwargs, _einfo):
        self.update_state(state=states.FAILURE)


@app.task(base=OnFailureStateTask)
def create_model_for_area():
    """Creates a model for the area"""
    initialise_db_with_region_geometries()


@app.task(base=OnFailureStateTask, ignore_result=True)
def initialise_db_with_region_geometries():
    run.main()
