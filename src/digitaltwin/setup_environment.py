# -*- coding: utf-8 -*-
"""
This module provides functions for connecting to a database using SQLAlchemy.
"""

import logging

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import OperationalError

from src import config

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(levelname)s:%(asctime)s:%(name)s:%(message)s')
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)

Base = declarative_base()


def get_database() -> Engine:
    """Set up the database connection. Exit the program if connection fails."""
    try:
        engine = get_connection_from_profile()
        log.debug("Connected to PostgreSQL database successfully!")
        return engine
    except OperationalError as e:
        raise ConnectionAbortedError("Connection to database failed. Please check .env file.") from e


def get_connection_from_profile() -> Engine:
    """Sets up database connection from configuration."""
    connection_keys = ["POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"]
    host, port, db, username, password = (config.get_env_variable(key) for key in connection_keys)

    if any(connection_cred is None for connection_cred in [host, port, db, username, password]):
        raise ValueError("Please check the .env file as one or more of the connection credentials are missing.")

    return get_engine(host, port, db, username, password)


def get_engine(host: str, port: str, db: str, username: str, password: str) -> Engine:
    """Get SQLAlchemy engine using credentials.

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
    """
    url = f'postgresql://{username}:{password}@{host}:{port}/{db}'
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    return engine


if __name__ == "__main__":
    get_database()
