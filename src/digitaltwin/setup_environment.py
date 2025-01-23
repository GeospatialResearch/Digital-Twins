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

"""
This script provides functions to set up the database connection using SQLAlchemy and environment variables,
as well as to create an SQLAlchemy engine for database operations.
"""

import logging

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.declarative import declarative_base

from src.config import EnvVariable

log = logging.getLogger(__name__)

Base = declarative_base()


def get_database() -> Engine:
    """
    Set up the database connection. Exit the program if connection fails.

    Returns
    -------
    Engine
        The engine used to connect to the database.

    Raises
    ------
    OperationalError
        If the connection to the database fails.
    """
    try:
        engine = get_connection_from_profile()
        log.debug("Connected to PostgreSQL database successfully!")
        return engine
    except OperationalError as e:
        raise OperationalError("Database connection failed. Please check database running and check .env file.",
                               params="",
                               orig=e,
                               hide_parameters=True) from e


def get_connection_from_profile() -> Engine:
    """
    Set up database connection from configuration.

    Returns
    -------
    Engine
        The engine used to connect to the database.
    """
    # Create and return the database engine
    return get_engine(EnvVariable.POSTGRES_HOST,
                      EnvVariable.POSTGRES_PORT,
                      EnvVariable.POSTGRES_DB,
                      EnvVariable.POSTGRES_USER,
                      EnvVariable.POSTGRES_PASSWORD)


def get_engine(host: str, port: str, db: str, username: str, password: str) -> Engine:
    """
    Get SQLAlchemy engine using credentials.

    Parameters
    ----------
    host : str
        Hostname of the database server.
    port : str
        Port number.
    db : str
        Database name.
    username : str
        Username.
    password : str
        Password for the database.

    Returns
    -------
    Engine
        The engine used to connect to the database.
    """
    url = f'postgresql://{username}:{password}@{host}:{port}/{db}'
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    return engine
