# -*- coding: utf-8 -*-
"""
Created on Thu Aug  5 17:09:13 2021.

@author: pkh35
"""

import logging
import sys
import yaml
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

log = logging.getLogger(__name__)


def get_database():
    """Exit the program if connection fails."""
    try:
        engine = get_connection_from_profile()
        log.info("Connected to PostgreSQL database!")
    except IOError:
        log.exception("Failed to get database connection!")
        sys.exit()
    return engine


def get_connection_from_profile(config_file_name="db_configure.yml"):
    """Set up database connection from config file.

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
