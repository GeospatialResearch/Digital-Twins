# -*- coding: utf-8 -*-
"""
Created on Thu Aug  5 17:09:13 2021.

@author: pkh35, sli229
"""

import logging
import sys
import yaml
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(levelname)s:%(asctime)s:%(name)s:%(message)s')
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def get_database():
    """Exit the program if connection fails."""
    try:
        engine = get_connection_from_profile()
        log.info("Connected to PostgreSQL database!")
        return engine
    except KeyError:
        log.exception("Failed to get PostgreSQL database connection!")
        sys.exit()


def get_connection_from_profile(config_file_name="db_configure.yml"):
    """Sets up database connection from config file.

    Input:
    config_file_name:File containing PGHOST, PGUSER,
                      PGPASSWORD, PGDATABASE, PGPORT, which are the
                      credentials for the PostgreSQL database
    """
    with open(config_file_name, 'r') as config_vals:
        vals = yaml.safe_load(config_vals)

    if not all(key in vals.keys() for key in ['PGHOST', 'PGUSER', 'PGPASSWORD', 'PGDATABASE', 'PGPORT']):
        raise KeyError('Bad config file: ' + config_file_name)
    else:
        return get_engine(vals['PGDATABASE'], vals['PGUSER'],
                          vals['PGHOST'], vals['PGPORT'],
                          vals['PGPASSWORD'])


def get_engine(db, user, host, port, passwd):
    """Get SQLalchemy engine using credentials.

    Input:
    db: database name
    user: Username
    host: Hostname of the database server
    port: Port number
    passwd: Password for the database
    """
    url = f'postgresql://{user}:{passwd}@{host}:{port}/{db}'
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    return engine
