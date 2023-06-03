# -*- coding: utf-8 -*-
"""
Created on Tue Aug 10 13:29:55 2021.

@author: pkh35, sli229
"""

import logging
from datetime import datetime
from typing import Tuple

import pandas as pd
import geoapis.vector

from geoalchemy2 import Geometry
from sqlalchemy import inspect, Column, Integer, DateTime, Unicode, Date
from sqlalchemy.engine import Engine
from sqlalchemy.dialects.postgresql import JSONB, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)

Base = declarative_base()


def region_geometry(key):
    """get the regional polygons data from Stats NZ and create a complete NZ polygon"""
    # fetch the required regional polygon data from StatsNZ
    vector_fetcher = geoapis.vector.StatsNz(key, verbose=True, crs=2193)
    response_data = vector_fetcher.run(105133)
    response_data.columns = response_data.columns.str.lower()
    # Move 'geometry' column to be the last column
    geometry_column = response_data.pop("geometry")
    response_data = pd.concat([response_data, geometry_column], axis=1)
    # Dissolve regional polygons to create complete NZ polygon then explode
    nz_polygon = response_data.dissolve(aggfunc="sum").explode(index_parts=True)
    nz_polygon.insert(0, "regc2021_v1_00", "100")
    nz_polygon.insert(1, "regc2021_v1_00_name", "New Zealand")
    nz_polygon.insert(2, "regc2021_v1_00_name_ascii", "New Zealand")
    # Combine regional polygons and complete NZ polygon
    region_geometry_df = pd.concat(
        [response_data, nz_polygon.iloc[[0]]], ignore_index=True
    )
    return region_geometry_df


class User_log_info(Base):
    """Class used to create user_log_information table."""

    __tablename__ = "user_log_information"
    unique_id = Column(Integer, primary_key=True, autoincrement=True)
    source_list = Column(JSONB)
    geometry = Column(Geometry("POLYGON"))
    accessed_date = Column(DateTime, default=datetime.now())


class Apilink(Base):
    """Class used to create apilinks table."""

    __tablename__ = "apilinks"
    unique_id = Column(Integer, primary_key=True, autoincrement=True)
    data_provider = Column(Unicode)
    source_name = Column(Unicode, unique=True)
    layer = Column(Integer)
    region_name = Column(Unicode)
    source_api = Column(Unicode)
    api_modified_date = Column(Date)
    url = Column(Unicode)
    access_date = Column(DateTime, default=datetime.now())
    query_dictionary = Column(JSON)
    geometry_col_name = Column(Unicode)
    geometry = Column(Geometry)


class dbsession:
    """Class used to connect to postgreSQL"""

    def sessionCreate(self, table, engine):
        # checkfirst=True to make sure the table doesn't exist
        table.__table__.create(engine, checkfirst=True)

    def runQuery(self, engine, query):
        Session = sessionmaker(bind=engine)
        session = Session()
        try:
            session.add(query)
            session.commit()
        except Exception as error:
            log.info(error)
            session.rollback()


def check_table_exists(engine: Engine, table_name: str, schema: str = "public") -> Tuple[str, bool]:
    """
    Check if table exists in the database.

    Parameters
    ----------
    engine : Engine
        Engine used to connect to the database.
    table_name : str
        The name of the table to check.
    schema : str = "public"
        Name of the schema where the table resides. Defaults to "public".

    Returns
    -------
    bool
        True if the table exists, False otherwise.
    """
    inspector = inspect(engine)
    return inspector.has_table(table_name, schema=schema)
