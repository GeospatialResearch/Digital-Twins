# -*- coding: utf-8 -*-
"""
Created on Thu Aug  5 17:09:13 2021.

@author: pkh35, sli229
"""

import logging

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base

from src import config

Base = declarative_base()

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(levelname)s:%(asctime)s:%(name)s:%(message)s')
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def get_database():
    """Exit the program if connection fails."""
    engine = get_connection_from_profile()
    log.info("Connected to PostgreSQL database!")
    return engine


def get_connection_from_profile():
    """Sets up database connection from config file."""
    connection_keys = ["POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"]
    host, port, db, username, password = (config.get_env_variable(key) for key in connection_keys)

    if any(connection_cred is None for connection_cred in [host, port, db, username, password]):
        raise ConnectionAbortedError(f"Bad .env file. Not all f{connection_keys} set.")

    return get_engine(db, username, host, port, password)


def get_engine(db: str, user: str, host: str, port: str, password: str):
    """Get SQLalchemy engine using credentials.

    Input:
    db: database name
    user: Username
    host: Hostname of the database server
    port: Port number
    passwd: Password for the database
    """
    url = f'postgresql://{user}:{password}@{host}:{port}/{db}'
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    return engine
