# -*- coding: utf-8 -*-
"""
Created on Tue Aug 10 13:29:55 2021.

@author: pkh35, sli229
"""
from datetime import datetime
from geoalchemy2 import Geometry
from sqlalchemy import Column, Integer, DateTime, Unicode, Date
from sqlalchemy.dialects.postgresql import JSONB, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import sqlalchemy
import geoapis.vector
import pandas as pd
import logging

Base = declarative_base()

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


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


def table_exists(engine, name, schema="public"):
    """Check whether table already exist in the database"""
    check_exists = sqlalchemy.inspect(engine).has_table(name, schema)
    return check_exists
