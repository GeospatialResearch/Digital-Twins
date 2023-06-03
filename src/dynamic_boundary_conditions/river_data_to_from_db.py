import logging
import pathlib

import geopandas as gpd
import pandas as pd
import sqlalchemy
import geoapis.vector
from sqlalchemy.engine import Engine

from src import config

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def check_table_exists(engine: Engine, db_table_name: str) -> bool:
    """
    Check if table exists in the database.

    Parameters
    ----------
    engine : Engine
        Engine used to connect to the database.
    db_table_name : str
        Database table name.
    """
    insp = sqlalchemy.inspect(engine)
    table_exists = insp.has_table(db_table_name, schema="public")
    return table_exists


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
    if check_table_exists(engine, "rec1_data"):
        log.info("Table 'rec1_data' already exists in the database.")
    else:
        rec1_nz = get_rec1_data_from_niwa(rec1_data_dir)
        rec1_nz.to_postgis("rec1_data", engine, index=False, if_exists="replace")
        log.info("Added REC1 data to database.")


def get_data_from_mfe(
        layer_id: int,
        crs: int = 2193,
        bounding_polygon: gpd.GeoDataFrame = None,
        verbose: bool = True) -> gpd.GeoDataFrame:
    mfe_api_key = config.get_env_variable("MFE_API_KEY")
    vector_fetcher = geoapis.vector.WfsQuery(
        key=mfe_api_key,
        crs=crs,
        bounding_polygon=bounding_polygon,
        netloc_url="data.mfe.govt.nz",
        geometry_names=['GEOMETRY', 'shape'],
        verbose=verbose)
    vector_layer_data = vector_fetcher.run(layer_id)
    return vector_layer_data


def store_sea_drain_catchments_to_db(
        engine: Engine,
        layer_id: int = 99776,
        crs: int = 2193,
        bounding_polygon: gpd.GeoDataFrame = None,
        verbose: bool = True) -> None:
    if check_table_exists(engine, "sea_draining_catchments"):
        log.info("Table 'sea_draining_catchments' already exists in the database.")
    else:
        sdc_data = get_data_from_mfe(layer_id, crs, bounding_polygon, verbose)
        sdc_data.columns = sdc_data.columns.str.lower()
        sdc_data = sdc_data[['catch_id', 'shape_leng', 'shape_area', 'geometry']]
        sdc_data.to_postgis("sea_draining_catchments", engine, index=False, if_exists="replace")
        log.info("Added Sea-draining Catchments data to database.")


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
