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
import traceback
from typing import Dict, Tuple

import billiard.einfo
import geopandas as gpd
import shapely
import sqlalchemy.exc
from celery import Celery, states

from src.config import EnvVariable
from src.digitaltwin import retrieve_from_instructions
from src.digitaltwin.utils import retry_function, setup_logging

# Setup celery backend task management
message_broker_url = f"redis://{EnvVariable.MESSAGE_BROKER_HOST}:6379/0"
app = Celery("tasks", backend=message_broker_url, broker=message_broker_url)

setup_logging()
log = logging.getLogger(__name__)


class OnFailureStateTask(app.Task):
    """Task that switches state to FAILURE if an exception occurs."""  # pylint: disable=too-few-public-methods

    # noinspection PyIncorrectDocstring
    def on_failure(self,
                   exc: Exception,
                   _task_id: str,
                   _args: Tuple,
                   _kwargs: Dict,
                   _einfo: billiard.einfo.ExceptionInfo) -> None:
        """
        Change state to FAILURE and add exception to task data if an exception occurs.

        Parameters
        ----------
        exc : Exception
            The exception raised by the task.
        """
        self.update_state(state=states.FAILURE, meta={
            "exc_type": type(exc).__name__,
            "exc_message": traceback.format_exc().split('\n'),
            "extra": None
        })


@app.task(base=OnFailureStateTask)
def add_base_data_to_db(selected_polygon_wkt: str, base_data_parameters: Dict[str, str]) -> None:
    """
    Task to ensure static base data for the given area is added to the database.

    Parameters
    ----------
    selected_polygon_wkt : str
        The polygon defining the selected area to add base data for. Defined in WKT form.
    base_data_parameters : Dict[str, str]
        The parameters from DEFAULT_MODULES_TO_PARAMETERS[retrieve_from_instructions] for the particular module.
    """
    selected_polygon = wkt_to_gdf(selected_polygon_wkt)
    # Set up retry/timeout controls
    retries = 3
    delay_seconds = 30
    # Try to initialise db, with a retry set up in case of database exceptions that happen when concurrent access occurs
    retry_function(retrieve_from_instructions.main,
                   retries,
                   delay_seconds,
                   sqlalchemy.exc.IntegrityError,
                   selected_polygon,
                   **base_data_parameters)


def wkt_to_gdf(wkt: str) -> gpd.GeoDataFrame:
    """
    Transform a WKT string polygon into a GeoDataFrame.

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


# These must be imported after app to remove a circular dependency
import floodresilience.tasks  # pylint: disable=wrong-import-position,unused-import # noqa: E402, F401
