# -*- coding: utf-8 -*-
"""
Created on Tue Aug 10 13:29:55 2021.

@author: pkh35
"""
from datetime import datetime
from geoalchemy2 import Geometry
from sqlalchemy import Column, Integer, DateTime, Unicode, Date
from sqlalchemy.dialects.postgresql import JSONB, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
import geoapis.vector
Base = declarative_base()


class User_log_info(Base):
    """Class to create tables."""

    __tablename__ = 'user_log_information'
    unique_id = Column(Integer, primary_key=True, autoincrement=True)
    source_list = Column(JSONB)
    geometry = Column(Geometry('POLYGON'))
    accessed_date = Column(DateTime(timezone=True), default=func.now())


class Apilink(Base):
    __tablename__ = 'apilinks'
    data_provider = Column(Unicode)
    source_name = Column(Unicode, primary_key=True, unique=True)
    source_apis = Column(Unicode)
    url = Column(Unicode)
    api_modified_date = Column(Date)
    region_name = Column(Unicode)
    access_date = Column(DateTime, default=datetime.now())
    query_dictionary = Column(JSON)
    layer = Column(Unicode)
    geometry_col_name = Column(Unicode)
    geometry = Column(Geometry)


class dbsession():
    """Class to connect to postgreSQL"""

    def sessionCreate(self, table, engine):
        table.__table__.create(engine, checkfirst=True)

    def runQuery(self, engine, query):
        Session = sessionmaker(bind=engine)
        session = Session()
        try:
            session.add(query)
            session.commit()
        except Exception as error:
            print(error)
            session.rollback()


def table_exists(engine, name):
    ret = engine.dialect.has_table(engine, name)
    return ret


def region_geometry(key):
    """get the regional polygons data from Stats NZ
    and creating a polygon of complete NZ"""
    vector_fetcher = geoapis.vector.StatsNz(key, verbose=True)
    response_data = vector_fetcher.run(105133)
    response_data.columns = response_data.columns.str.lower()
    response_data['geometry'] = response_data.geometry.to_crs("EPSG:2193")
    nz_polygon = response_data.dissolve().explode()
    nz_polygon['regc2021_v1_00_name'] = "New Zealand"
    response_data = response_data.append(nz_polygon.iloc[0], ignore_index=True)
    return response_data
