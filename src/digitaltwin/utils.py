# -*- coding: utf-8 -*-
"""
@Date: 16/06/2023
@Author: sli229
"""

import geopandas as gpd
from shapely.geometry import Polygon


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


def get_catchment_area_polygon(catchment_area: gpd.GeoDataFrame, to_crs: int = 2193) -> Polygon:
    """
    Retrieve the polygon representing the catchment area.

    Parameters
    ----------
    catchment_area : gpd.GeoDataFrame
        The GeoDataFrame representing the catchment area.
    to_crs : int, optional
        Coordinate Reference System (CRS) code to convert the catchment area to. Default is 2193.

    Returns
    -------
    Polygon
        The polygon from the catchment area GeoDataFrame, converted to the specified CRS.
    """
    # Convert the catchment area to the specified CRS
    catchment_area_crs = catchment_area.to_crs(to_crs)
    # Extract the first polygon from the geometry column
    catchment_polygon = catchment_area_crs["geometry"].iloc[0]
    return catchment_polygon
