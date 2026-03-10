# -*- coding: utf-8 -*-
# Copyright © 2021-2026 Geospatial Research Institute Toi Hangarau
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
This script checks the cache for a matching model output for given input parameters,
and retrieves the model_id if a match is found.
"""

import json
import logging

import geopandas as gpd
from sqlalchemy.sql import text

from eddie.digitaltwin import setup_environment
from eddie.digitaltwin.utils import LogLevel, setup_logging
from eddie.digitaltwin.tables import check_table_exists

log = logging.getLogger(__name__)


def main(selected_polygon: gpd.GeoDataFrame, scenario_options: dict) -> int | None:
    """
    Search the cache for model input generated with identical scenario_options and a selected polygon which contains
    this function's selected_polygon.

    Parameters
    ----------
    selected_polygon : gpd.GeoDataFrame
        The area of interest to search the cache for. Positive results if the cached polygon contains this polygon.
    scenario_options : dict
        The model input parameters, which must match exactly with the cached results for a positive match.

    Returns
    -------
    int | None
        Returns the matching model_id if a match is found. Otherwise, None.
    """
    setup_logging(log_level=LogLevel.DEBUG)

    engine = setup_environment.get_database()
    # Check table exists before querying
    if not check_table_exists(engine, "cache_results"):
        return None

    log.info("Checking cache for matching model parameters")
    # Query for the matching cache
    query = text("""
        SELECT *
        FROM cache_results
        WHERE scenario_options::jsonb = cast(:scenario_options as jsonb)
        AND st_contains(geometry, st_geomfromtext(:aoi_polygon, 2193))
     """).bindparams(scenario_options=json.dumps(scenario_options), aoi_polygon=selected_polygon.geometry.iloc[0].wkt)
    row = engine.execute(query).fetchone()

    if row is None:  # If the row is empty then we could not find the model output
        log.info("No matching model parameters found")
        log.debug(query)
        return None
    # Return the matching model_id if a cache is found
    model_id = row["flood_model_id"]
    log.info(f"Matching model parameters found, output id {model_id}")
    return model_id
