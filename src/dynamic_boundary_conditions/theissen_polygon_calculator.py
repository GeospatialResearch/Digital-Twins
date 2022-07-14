# -*- coding: utf-8 -*-
"""
Created on Thu Jan 20 11:36:07 2022

@author: pkh35
"""

import pandas as pd
import geopandas as gpd
from geovoronoi import voronoi_regions_from_coords, points_to_coords
import geopandas
import pyproj
from shapely.ops import transform
import sys


def theissen_polygons(engine, catchment: geopandas.GeoDataFrame, gauges_in_polygon: geopandas.GeoDataFrame):
    """Calculate the area covered by each gauging site and store it in the database.

    catchment: get the geopandas dataframe of the catchment area.
    gauges_in_polygon: get the gauges data in the form of geopandas dataframe.
    """
    if catchment.empty or gauges_in_polygon.empty:
        print("No data available for the catchment or gauges passed as an argument.")
        sys.exit()
    else:
        catchment_area = catchment.geom[0]
        coords = points_to_coords(gauges_in_polygon.geometry)
        region_polys, region_pts = voronoi_regions_from_coords(coords, catchment_area, per_geom=False)

        sites_list = []
        for key, value in region_pts.items():
            site = gauges_in_polygon.loc[(gauges_in_polygon['order'] == value[0])]
            sites_list.append(site)
        sites_in_catchment = pd.concat(sites_list)

        wgs84 = pyproj.CRS('EPSG:4326')
        utm = pyproj.CRS('EPSG:3857')
        project = pyproj.Transformer.from_crs(wgs84, utm, always_xy=True).transform
        gauges_area = gpd.GeoDataFrame()
        sites = []
        area = []
        geometry = []

        for i, ind in zip(range(len(region_polys)), sites_in_catchment.index):
            projected_area = transform(project, region_polys[i]).area
            sites.append(sites_in_catchment['site_id'][ind])
            area.append(projected_area*0.001)
            geometry.append((region_polys[i]))

        gauges_area['site_id'] = sites
        gauges_area['area_in_km'] = area
        gauges_area['geometry'] = geometry
        gauges_area.to_postgis("gauges_area", engine, if_exists='replace')


if __name__ == "__main__":
    from src.digitaltwin import setup_environment
    from src.dynamic_boundary_conditions import hirds_gauges
    engine = setup_environment.get_database()
    catchment = hirds_gauges.get_new_zealand_boundary(engine)
    gauges_in_polygon = hirds_gauges.get_gauges_location(engine, catchment)
    theissen_polygons(engine, catchment, gauges_in_polygon)
