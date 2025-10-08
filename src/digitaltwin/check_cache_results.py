import geopandas as gpd
import pathlib
import json
import logging

import geopandas as gpd
from sqlalchemy import insert, select
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import text, bindparam

from src.digitaltwin import setup_environment, instructions_records_to_db, data_to_db
from src.digitaltwin.utils import LogLevel, setup_logging, get_catchment_area
from src.digitaltwin.tables import CacheResults, create_table, check_table_exists

log = logging.getLogger(__name__)
def main(selected_polygon: gpd.GeoDataFrame, scenario_options: dict) -> int | None:
    setup_logging(log_level=LogLevel.DEBUG)

    query = text("""
        SELECT *
        FROM cache_results
        WHERE scenario_options::jsonb = cast(:scenario_options as jsonb)
        AND st_contains(geometry, st_geomfromtext(:aoi_polygon, 2193))
     """).bindparams(scenario_options=json.dumps(scenario_options), aoi_polygon=selected_polygon.geometry.iloc[0].wkt)

    engine = setup_environment.get_database()
    # Check table exists before querying
    if not check_table_exists(engine, "cache_results"):
        return None
    log.info("Checking cache for matching model parameters")
    row = engine.execute(query).fetchone()
    # If the row is empty then we could not find the model output
    if row is None:
        log.info("No matching model parameters found")
        log.debug(query)
        return None
    model_id = row["flood_model_id"]
    log.info(f"Matching model parameters found, output id {model_id}")
    return model_id