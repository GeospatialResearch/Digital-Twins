# -*- coding: utf-8 -*-
# Copyright © 2021-2025 Geospatial Research Institute Toi Hangarau
# LICENSE: https://github.com/GeospatialResearch/Digital-Twins/blob/master/LICENSE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Runs backend tasks using Celery. Allowing for multiple long-running tasks to complete in the background.
Allows the frontend to send tasks and retrieve status later.
"""
import logging
from typing import Dict, List, NamedTuple, Union

from celery import result, signals
from celery.worker.consumer import Consumer
import geopandas as gpd
from pyproj import Transformer
import xarray

from src.digitaltwin import setup_environment, retrieve_from_instructions
from src.digitaltwin.utils import setup_logging
from src.tasks import add_base_data_to_db, app, OnFailureStateTask, wkt_to_gdf  # pylint: disable=cyclic-import
from watertracing import serve_outputs

setup_logging()
log = logging.getLogger(__name__)


@signals.worker_ready.connect
def on_startup(sender: Consumer, **_kwargs: None) -> None:  # pylint: disable=missing-param-doc
    """
    Initialise database, runs when Celery instance is ready.

    Parameters
    ----------
    sender : Consumer
        The Celery worker node instance
    """
    with sender.app.connection() as conn:
        # Gather area of interest from file.
        aoi_wkt = gpd.read_file("selected_polygon.geojson").to_crs(4326).geometry[0].wkt
        # Send a task to initialise this area of interest.
        base_data_parameters = DEFAULT_MODULES_TO_PARAMETERS[retrieve_from_instructions]
        sender.app.send_task("src.tasks.add_base_data_to_db", args=[aoi_wkt, base_data_parameters], connection=conn)
        # Send a task to ensure lidar datasets are evaluated.
        sender.app.send_task("watertracing.tasks.upload_water_tracing_data")


@app.task(base=OnFailureStateTask)
def upload_water_tracing_data() -> None:
    """
    Task to ensure model output data for water tracing is uploaded to geoserver.
    """
    parameters = DEFAULT_MODULES_TO_PARAMETERS[serve_outputs]
    watertracing.main(None, **parameters)
