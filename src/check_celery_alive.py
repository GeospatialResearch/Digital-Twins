"""Defines functions and decorators for checking if Celery worker is running."""
import logging
from functools import wraps
from http.client import SERVICE_UNAVAILABLE
from typing import Callable, Dict, Tuple

from flask import Response, make_response
from kombu.exceptions import OperationalError

from src import tasks


def check_celery_alive(f: Callable[..., Response]) -> Callable[..., Response]:
    """
    Check if the Celery workers are running and return INTERNAL_SERVER_ERROR if they are down using function decorator.

    Parameters
    ----------
    f : Callable[..., Response]
        The view function that is being decorated.

    Returns
    -------
    Callable[..., Response]
        Response is SERVICE_UNAVAILABLE if the celery workers are down, otherwise continue to function f
    """

    @wraps(f)
    def decorated_function(*args: Tuple, **kwargs: Dict) -> Response:
        """
        Before function `f` is called, check if Celery workers are down, and return and error response if so.
        If Celery workers are running, then continue with calling `f` with original arguments.

        Parameters
        ----------
        args : Tuple
            The original arguments for function `f`.
        kwargs : Dict
            The original keyword arguments for function `f`.

        Returns
        -------
        Response
            SERVICE_UNAVAILABLE if Celery workers are down, otherwise response from function `f`.
        """
        try:
            ping_celery_response = tasks.app.control.ping()
            if len(ping_celery_response) == 0:
                logging.warning("Celery workers not active, may indicate a fault")
                return make_response("Celery workers not active", SERVICE_UNAVAILABLE)
        except OperationalError:
            logging.warning("Celery workers not active, may indicate a fault")
            return make_response("Celery workers not active", SERVICE_UNAVAILABLE)
        return f(*args, **kwargs)

    return decorated_function
