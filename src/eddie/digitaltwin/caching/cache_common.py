"""
Generic process-result cache: table definition shared by `check_cache_results` and
`cache_new_results`, plus the canonicalisation/hashing helper used to key cache lookups.
"""

import hashlib
import json
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import Column, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB

from ..tables import Base

# Spatial containment reuse (treating a cached result for a larger AOI as valid for a
# smaller, fully-contained request) is a SCIENTIFIC claim about a specific process -
# "is it valid to reuse a result computed over a bigger area for a smaller area?" - not
# something the cache infrastructure can safely assume for every process. It must be
# declared explicitly, by process_id, by whoever owns that process's science.
#
# Add a process_id here only after confirming containment reuse is scientifically
# valid for that process.
SPATIAL_CONTAINMENT_OPT_IN: frozenset[str] = frozenset(
    {
        # This is explicitly empty, the modules and processes themselves should provide this functionality.
        # See issue https://github.com/GeospatialResearch/Digital-Twins/issues/412
    }
)


def supports_spatial_containment(process_id: str) -> bool:
    """
    Whether `process_id` has declared that a cached result computed for an AOI which
    contains the requested AOI may be reused (as opposed to requiring an exact AOI
    match).

    Parameters
    ----------
    process_id : str
        The process identifier to check.

    Returns
    -------
    bool
        True if `process_id` is opted in to spatial containment reuse.
    """
    return process_id in SPATIAL_CONTAINMENT_OPT_IN


def canonicalise_parameters(value: Any) -> str:
    """
    Produce a stable, canonical JSON string for `value` so that semantically identical
    parameter dicts (regardless of key order) hash to the same value.

    Parameters
    ----------
    value : Any
        A JSON-serialisable value (typically a dict of scenario/process parameters).

    Returns
    -------
    str
        Canonical JSON string with sorted keys and no incidental whitespace.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def compute_params_hash(process_parameters: dict) -> str:
    """
    Compute the SHA-256 hash used as the cache key for `process_parameters`.

    Parameters
    ----------
    process_parameters : dict
        The process input parameters to hash.

    Returns
    -------
    str
        Hex-encoded SHA-256 digest of the canonicalised process parameters.
    """
    canonical = canonicalise_parameters(process_parameters)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ProcessCache(Base):
    """
    Class representing the 'process_cache' table.
    Used to store parameters used for a process run and find matching cached outputs.

    Attributes
    ----------
    __tablename__ : str
        Name of the database table.
    id : int
        Unique identifier for each cache entry (primary key).
    process_id : str
        Identifies which process/pin produced the result, e.g. "fredt.flood_model",
        "smart_ideas.site_suitability". Used both for lookups and to key the spatial
        containment opt-in declared in SPATIAL_CONTAINMENT_OPT_IN.
    params_hash : str
        SHA-256 hex digest of the canonicalised `process_parameters` dict. Indexed for
        fast equality lookups without having to compare JSONB blobs directly.
    process_parameters : dict
        The raw process_parameters dict, kept for debugging/audit and to allow
        re-canonicalising if the hashing scheme ever changes.
    aoi : Polygon
        Optional area of interest. Nullable because not every process is spatial.
    input_version : dict
        Optional invalidation hook. A flexible JSONB blob rather than a single scalar
        so it can carry whatever a given process needs to decide "is this still valid",
        e.g.:
            {"dataset_ids": {"lidar": "nz-lidar-2024-v3"}}
            {"upstream_result_ids": [1234, 1235]}
            {"forecast_reference_time": "2026-10-06T12:00:00Z"}
        A cache lookup only matches rows whose input_version is exactly equal (by
        value, not identity) to the one supplied. Changing any part of it naturally
        invalidates old entries without needing an explicit purge.
    output_id : str
        Reference to the stored result that was produced (e.g. a model/job id, a row
        pk elsewhere, a file/object key). Stored as text to stay generic across
        processes rather than assuming an integer FK target.
    created_at : datetime
        Timestamp indicating when the cache entry was created.
    """  # pylint: disable=too-few-public-methods

    __tablename__ = "process_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)

    process_id = Column(String, nullable=False, index=True)
    params_hash = Column(String(64), nullable=False, index=True)
    process_parameters = Column(JSONB, nullable=False)

    aoi = Column(Geometry(geometry_type="POLYGON", srid=4326), nullable=True)
    input_version = Column(JSONB, nullable=True)

    output_id = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
