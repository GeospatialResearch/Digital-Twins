import logging
import pathlib

import geopandas as gpd
import pandas as pd
from sqlalchemy.engine import Engine

from src.digitaltwin import tables

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def get_rec1_data_from_niwa(
        rec1_data_dir: pathlib.Path,
        file_name: str = "NZ_Flood_Statistics_Henderson_Collins_V2_Layer.shp") -> gpd.GeoDataFrame:
    # Check if the REC1 data directory exists, if not, raise an error
    if not rec1_data_dir.exists():
        raise FileNotFoundError(f"REC1 data directory not found: {rec1_data_dir}")
    # Check if there are any Shape files in the specified directory
    if not any(rec1_data_dir.glob("*.shp")):
        raise FileNotFoundError(f"REC1 data files not found: {rec1_data_dir}")
    rec1_file_path = rec1_data_dir / file_name
    rec1_nz = gpd.read_file(rec1_file_path)
    rec1_nz.columns = rec1_nz.columns.str.lower()
    return rec1_nz


def store_rec1_data_to_db(engine: Engine, rec1_data_dir: pathlib.Path) -> None:
    table_name = "rec1_data"
    if tables.check_table_exists(engine, table_name):
        log.info(f"Table '{table_name}' already exists in the database.")
    else:
        rec1_nz = get_rec1_data_from_niwa(rec1_data_dir)
        rec1_nz.to_postgis(table_name, engine, index=False, if_exists="replace")
        log.info("Added REC1 data to database.")


def get_rec1_data_from_db(
        engine: Engine,
        catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    catchment_polygon = catchment_area["geometry"][0]
    sea_drain_query = f"""
    SELECT *
    FROM sea_draining_catchments AS sdc
    WHERE ST_Intersects(sdc.geometry, ST_GeomFromText('{catchment_polygon}', 2193))"""
    sdc_data = gpd.GeoDataFrame.from_postgis(sea_drain_query, engine, geom_col="geometry")
    sdc_polygon = sdc_data.unary_union
    sdc_area = gpd.GeoDataFrame(geometry=[sdc_polygon], crs=sdc_data.crs)
    combined_polygon = pd.concat([sdc_area, catchment_area]).unary_union
    rec1_query = f"""
    SELECT *
    FROM rec1_data AS rec
    WHERE ST_Intersects(rec.geometry, ST_GeomFromText('{combined_polygon}', 2193))"""
    rec1_data = gpd.GeoDataFrame.from_postgis(rec1_query, engine, geom_col="geometry")
    rec1_data = rec1_data.drop_duplicates()
    return rec1_data
