# -*- coding: utf-8 -*-
"""
This script contains SQLAlchemy models for various database tables and utility functions for database operations.
"""

from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import inspect, Column, String, Integer, DateTime
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

Base = declarative_base()


class GeospatialLayers(Base):
    """
    Class representing the 'geospatial_layers' table.

    Attributes
    ----------
    __tablename__ : str
        Name of the database table.
    unique_id : int
        Unique identifier for each geospatial layer entry (primary key).
    data_provider : str
        Name of the data provider.
    layer_id : int
        Identifier for the layer.
    table_name : str
        Name of the table containing the data.
    unique_column_name : str, optional
        Name of the unique column in the table.
    coverage_area : str, optional
        Coverage area of the geospatial data. It can be either the whole country or NULL.
    url : str
        URL pointing to the geospatial layer.
    """
    __tablename__ = "geospatial_layers"
    unique_id = Column(Integer, primary_key=True, autoincrement=True)
    data_provider = Column(String, nullable=False)
    layer_id = Column(Integer, nullable=False)
    table_name = Column(String, nullable=False)
    unique_column_name = Column(String, nullable=True)
    coverage_area = Column(String, nullable=True)
    url = Column(String, nullable=False)


class UserLogInfo(Base):
    """
    Class representing the 'user_log_information' table.

    Attributes
    ----------
    __tablename__ : str
        Name of the database table.
    unique_id : int
        Unique identifier for each log entry (primary key).
    source_table_list : List[str]
        A list of tables (geospatial layers) associated with the log entry.
    created_at : datetime
        Timestamp indicating when the log entry was created.
    geometry : Polygon
        Geometric representation of the catchment area coverage.
    """
    __tablename__ = "user_log_information"
    unique_id = Column(Integer, primary_key=True, autoincrement=True)
    source_table_list = Column(ARRAY(String), comment="associated tables (geospatial layers)")
    created_at = Column(DateTime(timezone=True), default=datetime.now(), comment="log created datetime")
    geometry = Column(Geometry("POLYGON", srid=2193))


class BGFloodModelOutput(Base):
    """
    Class representing the 'bg_flood_model_output' table.

    Attributes
    ----------
    __tablename__ : str
        Name of the database table.
    unique_id : int
        Unique identifier for each entry (primary key).
    file_name : str
        Name of the flood model output file.
    file_path : str
        Path to the flood model output file.
    created_at : datetime
        Timestamp indicating when the output was created.
    geometry : Geometry
        Geometric representation of the catchment area coverage.
    """
    __tablename__ = "bg_flood_model_output"
    unique_id = Column(Integer, primary_key=True, autoincrement=True)
    file_name = Column(String, comment="name of the flood model output file")
    file_path = Column(String, comment="path to the flood model output file")
    created_at = Column(DateTime(timezone=True), default=datetime.now(), comment="output created datetime")
    geometry = Column(Geometry("GEOMETRY", srid=2193))


def create_table(engine: Engine, table: Base) -> None:
    """
    Create a table in the database if it doesn't already exist, using the provided engine.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    table : Base
        Class representing the table to create.

    Returns
    -------
    None
        This function does not return any value.
    """
    table.__table__.create(bind=engine, checkfirst=True)


def check_table_exists(engine: Engine, table_name: str, schema: str = "public") -> bool:
    """
    Check if a table exists in the database.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    table_name : str
        The name of the table to check for existence.
    schema : str, optional
        The name of the schema where the table resides. Defaults to "public".

    Returns
    -------
    bool
        True if the table exists, False otherwise.
    """
    inspector = inspect(engine)
    return inspector.has_table(table_name, schema=schema)


def execute_query(engine: Engine, query) -> None:
    """
    Execute the given query on the provided engine using a session.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    query
        The query to be executed.

    Returns
    -------
    None
        This function does not return any value.

    Raises
    ------
    Exception
        If an error occurs during the execution of the query.
    """
    with Session(engine) as session:
        session.begin()
        try:
            session.add(query)
            session.commit()
        except Exception as error:
            session.rollback()
            raise error
