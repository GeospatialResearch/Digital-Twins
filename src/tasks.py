from celery import Celery

from .digitaltwin import run

message_broker_url = "redis://message_broker:6379/0"

app = Celery("tasks", backend=message_broker_url, broker=message_broker_url)


@app.task()
def create_model_for_area():
    initialise_db_with_region_geometries()


@app.task(ignore_result=True)
def initialise_db_with_region_geometries():
    run.main()
