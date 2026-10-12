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
Generic cache lookup, used by any process/pin to check whether a prior run already
produced a result for the given parameters (and, optionally, AOI / input_version).
"""

import json
import logging

import geopandas as gpd
from sqlalchemy.sql import text

from eddie.digitaltwin import setup_environment
from eddie.digitaltwin.caching.cache_common import (
    ProcessCache,
    canonicalise_parameters,
    compute_params_hash,
    supports_spatial_containment
)
from eddie.digitaltwin.tables import check_table_exists
from eddie.digitaltwin.utils import LogLevel, setup_logging

log = logging.getLogger(__name__)


def find_cached_result(
    process_id: str,
    process_parameters: dict,
    aoi: gpd.GeoDataFrame | None = None,
    input_version: dict | None = None,
) -> str | None:
    """
    Search the cache for a previously-stored result matching `process_id` and
    `process_parameters` exactly, and matching `aoi` / `input_version` according to the rules
    below.

    Parameters
    ----------
    process_id : str
        Identifier of the process/pin requesting the lookup, e.g. "fredt.flood_model".
    process_parameters : dict
        The process input process_parameters. Must match a cached entry exactly (after
        canonicalisation) for a hit.
    aoi : gpd.GeoDataFrame | None = None
        Area of interest to search for. If `process_id` has opted in to spatial
        containment reuse (see `cache_common.SPATIAL_CONTAINMENT_OPT_IN`), a cached
        entry whose AOI contains this one is considered a match. Otherwise an exact
        AOI match is required. If None, only rows with a null AOI are matched.
    input_version : dict | None = None
        Invalidation hook, e.g. dataset ids, upstream result references, or a
        forecast reference time. Must match a cached entry exactly for a hit; changing
        any part of it naturally invalidates stale cache entries. If None, only rows
        with a null input_version are matched.

    Returns
    -------
    str | None
        The matching `output_id` if a cache hit is found, otherwise None.
    """
    setup_logging(log_level=LogLevel.DEBUG)

    params_hash = compute_params_hash(process_parameters)

    engine = setup_environment.get_database()
    with engine.connect() as conn:
        if not check_table_exists(conn, ProcessCache.name):
            return None

        conditions = ["process_id = :process_id", "params_hash = :params_hash"]
        bind_params = {"process_id": process_id, "params_hash": params_hash}

        if input_version is not None:
            conditions.append("input_version::jsonb = cast(:input_version as jsonb)")
            # Set bind_params instead of writing condition directly, to avoid SQL Injection
            bind_params["input_version"] = canonicalise_parameters(input_version)
        else:
            conditions.append("input_version IS NULL")

        if aoi is not None:
            aoi_wkt = aoi.geometry.iloc[0].wkt
            # Set bind_params instead of writing condition directly, to avoid SQL Injection
            bind_params["aoi_wkt"] = aoi_wkt
            if supports_spatial_containment(process_id):
                conditions.append("ST_Contains(aoi, ST_SetSRID(ST_GeomFromText(:aoi_wkt), 4326))")
            else:
                conditions.append("ST_Equals(aoi, ST_SetSRID(ST_GeomFromText(:aoi_wkt), 4326))")
        else:
            conditions.append("aoi IS NULL")

        log.info("Checking cache for matching process parameters for process_id=%s", process_id)
        query = text(
            f"""
            SELECT output_id
            FROM {ProcessCache.name}
            WHERE {' AND '.join(conditions)}
            ORDER BY created_at DESC
            LIMIT 1
            """
        ).bindparams(**bind_params)
        row = conn.execute(query).fetchone()

    if row is None:
        log.info("No matching cached result found for process_id=%s", process_id)
        log.debug("process_parameters=%s", json.dumps(process_parameters))
        return None

    output_id = row.id
    log.info("Matching cached result found for process_id=%s, output_id=%s", process_id, output_id)
    return output_id
