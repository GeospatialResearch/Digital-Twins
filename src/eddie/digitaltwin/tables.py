# -*- coding: utf-8 -*-
# Copyright © 2021-2025 Geospatial Research Institute Toi Hangarau
# LICENSE: https://github.com/GeospatialResearch/Digital-Twins/blob/master/LICENSE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""This script contains SQLAlchemy models for various database tables and utility functions for database operations."""

from geoalchemy2 import Geometry
from sqlalchemy import Column, DateTime, func, inspect, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


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
    refresh_after : Optional[datetime]
        Expiry date after which the area covered by this log entry is considered stale for its 'aoi' fetch_mode
        source tables, and should be re-fetched rather than treated as already covered. Computed from the minimum
        'cache_length' of the source tables logged, at the time this entry was created. None means it never expires.
    geometry : Polygon
        Geometric representation of the area of interest coverage.
    """  # pylint: disable=too-few-public-methods

    __tablename__ = "user_log_information"
    unique_id = Column(Integer, primary_key=True, autoincrement=True)
    source_table_list = Column(ARRAY(String), comment="associated tables (geospatial layers)")
    # pylint: disable=not-callable # False-positive due to dynamic typing.
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="log created datetime")
    refresh_after = Column(DateTime(timezone=True), nullable=True, comment="Expiry date for this logged area's data")
    geometry = Column(Geometry("POLYGON", srid=4326))


def create_table(conn: Connection, table: Base) -> None:
    """
    Create a table in the database if it doesn't already exist, using the provided conn.

    Parameters
    ----------
    conn : Connection
        The connection used to connect to the database.
    table : Base
        Class representing the table to create.
    """
    table.__table__.create(bind=conn, checkfirst=True)


def check_table_exists(conn: Connection, table_name: str, schema: str = "public") -> bool:
    """
    Check if a table exists in the database.

    Parameters
    ----------
    conn : Connection
        The connection used to connect to the database.
    table_name : str
        The name of the table to check for existence.
    schema : str = "public"
        The name of the schema where the table resides. Defaults to "public".

    Returns
    -------
    bool
        True if the table exists, False otherwise.
    """
    inspector = inspect(conn)
    return inspector.has_table(table_name, schema=schema)


def execute_query(engine: Engine, query: Base) -> None:
    """
    Add the given ORM object (e.g. a new table row) to the database in its own session transaction.
    The transaction is committed on success and rolled back if an error occurs.

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    query : Base
        The ORM object to add, e.g. `UserLogInfo(source_table_list=[...], geometry=...)`.
    """
    with Session(engine) as session, session.begin():
        session.add(query)
