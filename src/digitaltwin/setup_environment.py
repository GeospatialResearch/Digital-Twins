# -*- coding: utf-8 -*-
"""
Created on Thu Aug  5 17:09:13 2021.

@author: pkh35, sli229
"""

import logging

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base

from src import config

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(levelname)s:%(asctime)s:%(name)s:%(message)s')
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)

Base = declarative_base()


def get_database() -> Engine:
    """Exit the program if connection fails."""
    engine = get_connection_from_profile()
    log.debug("Connected to PostgreSQL database!")
    return engine


def get_connection_from_profile() -> Engine:
    """Sets up database connection from config file."""
    connection_keys = ["POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"]
    host, port, db, username, password = (config.get_env_variable(key) for key in connection_keys)

    if any(connection_cred is None for connection_cred in [host, port, db, username, password]):
        raise ConnectionAbortedError(f"Bad .env file. Not all f{connection_keys} set.")

    return get_engine(host, port, db, username, password)


def get_engine(host: str, port: str, db: str, username: str, password: str) -> Engine:
    """Get sqlalchemy engine using credentials.

    Input:
    host: Hostname of the database server
    port: Port number
    db: Database name
    username: Username
    password: Password for the database
    """
    url = f'postgresql://{username}:{password}@{host}:{port}/{db}'
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    return engine
