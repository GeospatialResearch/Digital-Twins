# -*- coding: utf-8 -*-
"""This script contains SQLAlchemy models for various database tables and utility functions for database operations."""

from datetime import datetime, timezone

from geoalchemy2 import Geometry
from sqlalchemy import Column, DateTime, inspect, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, Query
from sqlalchemy.schema import CheckConstraint

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
    unique_column_name : Optional[str]
        Name of the unique column in the table.
    coverage_area : Optional[str]
        Coverage area of the geospatial data, e.g. 'New Zealand'.
    url : str
        URL pointing to the geospatial layer.
    """  # pylint: disable=too-few-public-methods

    __tablename__ = "geospatial_layers"
    unique_id = Column(Integer, primary_key=True, autoincrement=True)
    data_provider = Column(String, nullable=False)
    layer_id = Column(Integer, nullable=False)
    table_name = Column(String, nullable=False)
    unique_column_name = Column(String, nullable=True)
    coverage_area = Column(String, nullable=True)
    url = Column(String, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "((unique_column_name IS NOT NULL AND coverage_area IS NULL) OR "
            "(unique_column_name IS NULL AND coverage_area IS NOT NULL))",
            name="unique_column_name_or_coverage_area_required"
        ),
    )


class UserLogInfo(Base):
    """
    Class representing the 'user_log_information' table.

    Attributes
    ----------
    __tablename__ : str
        Name of the database table.
    unique_id : int
        Unique identifier for each log entry (primary key).
    source_table_list : Dict[str]
        A list of tables (geospatial layers) associated with the log entry.
    created_at : datetime
        Timestamp indicating when the log entry was created.
    geometry : Polygon
        Geometric representation of the catchment area coverage.
    """  # pylint: disable=too-few-public-methods

    __tablename__ = "user_log_information"
    unique_id = Column(Integer, primary_key=True, autoincrement=True)
    source_table_list = Column(ARRAY(String), comment="associated tables (geospatial layers)")
    created_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc), comment="log created datetime")
    geometry = Column(Geometry("POLYGON", srid=2193))


def define_custom_db_functions(engine: Engine) -> None:
    """
    Create custom SQL functions for the database, to aid in queries.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    """
    # Create function for calculating result as significant figures
    create_significant_figures_statement = """
        CREATE OR REPLACE FUNCTION sig_fig(n double precision, digits integer)
            RETURNS numeric
        AS
        $$
        SELECT CASE
                   WHEN n = 0 THEN 0
                   ELSE round(n::numeric, digits - 1 - floor(log(abs(n)))::int)
                   END
        $$ LANGUAGE sql IMMUTABLE
                        STRICT;
    """
    engine.execute(create_significant_figures_statement)


def create_table(engine: Engine, table: Base) -> None:
    """
    Create a table in the database if it doesn't already exist, using the provided engine.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    table : Base
        Class representing the table to create.
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
    schema : str = "public"
        The name of the schema where the table resides. Defaults to "public".

    Returns
    -------
    bool
        True if the table exists, False otherwise.
    """
    inspector = inspect(engine)
    return inspector.has_table(table_name, schema=schema)


def execute_query(engine: Engine, query: Query) -> None:
    """
    Execute the given query on the provided engine using a session.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    query : Query
        The query to be executed.

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
