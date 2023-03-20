# -*- coding: utf-8 -*-
"""
@Description:
@Author: sli229
"""

import logging
import pathlib
from typing import Tuple
import sqlalchemy
from shapely.geometry import Polygon

import geopandas as gpd
import geoapis.vector

from src import config
from src.digitaltwin import setup_environment

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def catchment_area_geometry_info(catchment_file: pathlib.Path) -> Polygon:
    """
    Extract shapely geometry polygon from the catchment file.

    Parameters
    ----------
    catchment_file
        The file path of the catchment polygon shapefile.
    """
    catchment = gpd.read_file(catchment_file)
    catchment = catchment.to_crs(4326)
    catchment_polygon = catchment["geometry"][0]
    return catchment_polygon


def get_catchment_centroid_coords(catchment_file: pathlib.Path) -> Tuple[float, float]:
    """
    Extract the catchment polygon centroid coordinates.

    Parameters
    ----------
    catchment_file : pathlib.Path
        The file path for the catchment polygon.
    """
    catchment_polygon = catchment_area_geometry_info(catchment_file)
    long, lat = catchment_polygon.centroid.coords[0]
    return lat, long
