# -*- coding: utf-8 -*-
"""
@Description:
@Author: sli229
"""

import pathlib
from typing import Tuple

import geopandas as gpd


def get_catchment_centroid_coords(catchment_file: pathlib.Path) -> Tuple[float, float]:
    """
    Extract the catchment polygon centroid coordinates.

    Parameters
    ----------
    catchment_file : pathlib.Path
        The file path for the catchment polygon.
    """
    catchment = gpd.read_file(catchment_file)
    catchment = catchment.to_crs(4326)
    catchment_polygon = catchment["geometry"][0]
    long, lat = catchment_polygon.centroid.coords[0]
    return lat, long
