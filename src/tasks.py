from typing import List

from celery import Celery
from celery.result import AsyncResult


message_broker_url = "redis://message_broker:6379/0"

app = Celery("tasks", backend=message_broker_url, broker=message_broker_url)


@app.task(track_started=True, ignore_result=False)
def add(numbers: List[int]):
    return sum(numbers)
