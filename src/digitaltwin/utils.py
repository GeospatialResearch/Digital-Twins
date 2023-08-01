# -*- coding: utf-8 -*-
"""
@Description: This script provides utility functions for logging configuration and geospatial data manipulation.
@Author: sli229
"""

import logging

import geopandas as gpd
from sqlalchemy.engine import Engine


def setup_logging(log_level: int = logging.DEBUG) -> None:
    """
    Configure the root logger with the specified log level and format, and exclude specific loggers from propagating
    their messages to the root logger.

    Parameters
    ----------
    log_level : int, optional
        The log level to set for the root logger. Defaults to logging.DEBUG.
        The available logging levels and their corresponding numeric values are:
        - logging.CRITICAL (50)
        - logging.ERROR (40)
        - logging.WARNING (30)
        - logging.INFO (20)
        - logging.DEBUG (10)
        - logging.NOTSET (0)

    Returns
    -------
    None
        This function does not return any value.
    """
    # Check if handlers already exist and remove them if needed
    if logging.root.handlers:
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
    # Create a logging format
    logging_format = '%(levelname)s:%(asctime)s:%(name)s:%(message)s'
    # Create and configure the root logger with the specified log level and format
    logging.basicConfig(level=log_level, format=logging_format)
    # List of loggers to prevent messages from reaching the root logger
    loggers_to_exclude = ["urllib3", "fiona", "botocore", "pyproj", "asyncio", "rasterio"]
    # Iterate through the loggers to exclude
    for logger_name in loggers_to_exclude:
        # Get the logger instance for each name in the list
        logger = logging.getLogger(logger_name)
        # Disable log message propagation from these loggers to the root logger
        logger.propagate = False


def get_catchment_area(catchment_area: gpd.GeoDataFrame, to_crs: int = 2193) -> gpd.GeoDataFrame:
    """
    Convert the coordinate reference system (CRS) of the catchment area GeoDataFrame to the specified CRS.

    Parameters
    ----------
    catchment_area : gpd.GeoDataFrame
        The GeoDataFrame representing the catchment area.
    to_crs : int, optional
        Coordinate Reference System (CRS) code to convert the catchment area to. Default is 2193.

    Returns
    -------
    gpd.GeoDataFrame
        The catchment area GeoDataFrame with the transformed CRS.
    """
    return catchment_area.to_crs(to_crs)


def get_nz_boundary(engine: Engine, to_crs: int = 2193) -> gpd.GeoDataFrame:
    """
    Get the boundary of New Zealand in the specified Coordinate Reference System (CRS).

    Parameters
    ----------
    engine : Engine
        The engine used to connect to the database.
    to_crs : int, optional
        Coordinate Reference System (CRS) code to which the boundary will be converted. Default is 2193.

    Returns
    -------
    gpd.GeoDataFrame
        A GeoDataFrame representing the boundary of New Zealand in the specified CRS.
    """
    # Query the 'region_geometry' table from the database using the provided engine
    query = "SELECT * FROM region_geometry;"
    region_geometry = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry")
    # Dissolve and explode the geometries to get the boundary of New Zealand
    nz_boundary = region_geometry.dissolve(aggfunc="sum").explode(index_parts=True).reset_index(level=0, drop=True)
    # Calculate the area of each geometry and sort them in descending order
    nz_boundary["geometry_area"] = nz_boundary["geometry"].area
    nz_boundary = nz_boundary.sort_values(by="geometry_area", ascending=False).head(1)
    # Convert to the desired coordinate reference system (CRS)
    nz_boundary = nz_boundary.to_crs(to_crs)
    return nz_boundary
