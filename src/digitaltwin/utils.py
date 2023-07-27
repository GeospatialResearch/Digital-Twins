# -*- coding: utf-8 -*-
"""
@Date: 16/06/2023
@Author: sli229
"""

import geopandas as gpd
from shapely.geometry import Polygon
from sqlalchemy.engine import Engine


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


def get_nz_boundary_polygon(engine: Engine, to_crs: int = 2193) -> Polygon:
    """
    Get the boundary polygon of New Zealand.

    Parameters
    ----------
    engine : Engine
        Engine used to connect to the database.
    to_crs : int, optional
        Coordinate Reference System (CRS) code to convert the boundary polygon to. Default is 2193.

    Returns
    -------
    Polygon
        The boundary polygon of New Zealand in the specified CRS.
    """
    # Query the region_geometry table from the database using the provided engine
    query = "SELECT * FROM region_geometry;"
    region_geometry = gpd.GeoDataFrame.from_postgis(query, engine, geom_col="geometry")
    # Dissolve and explode the geometries
    nz_boundary = region_geometry.dissolve(aggfunc="sum").explode(index_parts=True).reset_index(level=0, drop=True)
    # Calculate the area of each geometry and sort them in descending order
    nz_boundary["geometry_area"] = nz_boundary["geometry"].area
    nz_boundary = nz_boundary.sort_values(by="geometry_area", ascending=False).head(1)
    # Convert to the desired coordinate reference system (CRS) and get the Polygon
    nz_boundary = nz_boundary.to_crs(to_crs)
    nz_boundary_polygon = nz_boundary["geometry"][0]
    return nz_boundary_polygon
