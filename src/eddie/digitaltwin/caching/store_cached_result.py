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
Generic cache store, used by any process/pin to record that a given set of parameters
(and, optionally, AOI / input_version) produced a particular output.
"""

import logging

import geopandas as gpd
from sqlalchemy import insert

from eddie.digitaltwin import setup_environment
from eddie.digitaltwin.caching.cache_common import ProcessCache, compute_params_hash
from eddie.digitaltwin.tables import create_table
from eddie.digitaltwin.utils import LogLevel, setup_logging

log = logging.getLogger(__name__)


def store_cached_result(
    process_id: str,
    process_parameters: dict,
    output_id: str,
    aoi: gpd.GeoDataFrame | None = None,
    input_version: dict | None = None,
    log_level: LogLevel = LogLevel.INFO,
) -> str:
    """
    Cache `output_id` against `process_id` + `process_parameters`
    (and, optionally, `aoi` / `input_version`) for faster retrieval later via `find_cached_result`.

    Parameters
    ----------
    process_id : str
        Identifier of the process/pin storing the result, e.g. "fredt.flood_model".
    process_parameters : dict
        The process input parameters that produced `output_id`. Canonicalised and
        hashed for later exact-match lookup.
    output_id : str
        Reference to the result to cache (e.g. a model/job id, a row pk, a file key).
    aoi : gpd.GeoDataFrame | None = None
        Area of interest the result was computed for, if applicable.
    input_version : dict | None = None
        Invalidation hook for this entry, e.g. dataset ids, upstream result
        references, or a forecast reference time (see `cache_common.ProcessCache`).
    log_level : LogLevel = LogLevel.INFO
        The log level to set for the root logger. Defaults to LogLevel.INFO.

    Returns
    -------
    str
        `output_id` re-returned to allow method chaining.
    """
    setup_logging(log_level)

    params_hash = compute_params_hash(process_parameters)
    aoi_ewkt = None
    if aoi is not None:
        aoi_ewkt = f"SRID=4326;{aoi.geometry.iloc[0].wkt}"

    engine = setup_environment.get_database()
    with engine.connect() as conn:
        create_table(conn, ProcessCache)

        log.info("Caching result output_id=%s for process_id=%s", output_id, process_id)
        query = insert(ProcessCache).values(
            process_id=process_id,
            params_hash=params_hash,
            process_parameters=process_parameters,
            aoi=aoi_ewkt,
            input_version=input_version,
            output_id=str(output_id),
        )
        conn.execute(query)
        conn.commit()

    return output_id
