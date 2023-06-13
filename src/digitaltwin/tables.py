# -*- coding: utf-8 -*-
"""
Created on Tue Aug 10 13:29:55 2021.

@author: pkh35, sli229
"""

import logging
from datetime import datetime

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


def check_table_exists(engine: Engine, table_name: str, schema: str = "public") -> bool:
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
