# -*- coding: utf-8 -*-
"""
@Description:
@Author: sli229
"""

import geopandas as gpd
from shapely.geometry import Polygon


def get_catchment_area(catchment_area: gpd.GeoDataFrame, to_crs: int = 2193) -> gpd.GeoDataFrame:
    catchment_area = catchment_area.to_crs(to_crs)
    return catchment_area


def get_catchment_area_polygon(catchment_area: gpd.GeoDataFrame, to_crs: int = 2193) -> Polygon:
    """
    Extract shapely geometry polygon from the catchment boundary in the given crs

    Parameters
    ----------
    catchment_area
        Catchment area GeoPandas data frame.
    to_crs: int = 4326
        Specify the output's coordinate reference system. Default is 2193.
    """
    return catchment_area.to_crs(to_crs)["geometry"][0]
