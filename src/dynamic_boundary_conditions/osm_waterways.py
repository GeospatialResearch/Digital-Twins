import logging

import geopandas as gpd
from OSMPythonTools.cachingStrategy import CachingStrategy, JSON
from OSMPythonTools.overpass import overpassQueryBuilder, Overpass

from src.dynamic_boundary_conditions import main_river


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)

log.addHandler(stream_handler)


def get_waterways_data_from_osm(catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    catchment_area = catchment_area.to_crs(4326)
    # Get the bounding box coordinates
    min_x, min_y, max_x, max_y = catchment_area.bounds.values[0]
    # change the path where the files are stored
    CachingStrategy.use(JSON, cacheDir='U:/Research/FloodRiskResearch/DigitalTwin/stored_data/osm_cache')
    # Construct query
    query = overpassQueryBuilder(
        bbox=[min_y, min_x, max_y, max_x],
        elementType="way",
        selector="waterway",
        out="body",
        includeGeometry=True
    )
    # Perform query
    waterways = Overpass().query(query, timeout=600)
    # Extract information
    element_dict = {
        "id": [],
        "waterway": [],
        "geometry": []
    }
    for element in waterways.elements():
        element_dict["id"].append(element.id())
        element_dict["waterway"].append(element.tag("waterway"))
        element_dict["geometry"].append(element.geometry())

    osm_waterways = gpd.GeoDataFrame(element_dict, crs=4326).to_crs(2193)
    osm_waterways = osm_waterways[osm_waterways["geometry"].type == "LineString"]
    osm_waterways_data = osm_waterways.loc[
        (osm_waterways['waterway'] == 'river') | (osm_waterways['waterway'] == 'stream')]
    osm_waterways_data = osm_waterways_data.reset_index(drop=True)
    return osm_waterways_data


def get_osm_boundary_points_on_bbox(
        catchment_area: gpd.GeoDataFrame,
        osm_waterways_data: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    catchment_boundary = catchment_area.exterior.iloc[0]
    osm_bound_points_on_bbox = (
        osm_waterways_data[osm_waterways_data.intersects(catchment_boundary)].reset_index(drop=True))
    osm_bound_points = []
    for _, row in osm_bound_points_on_bbox.iterrows():
        geometry = row["geometry"]
        boundary_point = catchment_boundary.intersection(geometry) if catchment_boundary.intersects(geometry) else None
        osm_bound_points.append(boundary_point)
    osm_bound_points_on_bbox["boundary_point"] = gpd.GeoSeries(
        osm_bound_points, crs=osm_bound_points_on_bbox["geometry"].crs)
    osm_bound_points_on_bbox["boundary_point_centre"] = osm_bound_points_on_bbox["boundary_point"].centroid
    osm_bound_points_on_bbox = osm_bound_points_on_bbox.set_geometry("boundary_point_centre")
    osm_bound_points_on_bbox.rename(columns={'geometry': 'osm_waterway_line'}, inplace=True)
    return osm_bound_points_on_bbox


def get_osm_waterways_data_on_bbox(
        catchment_area: gpd.GeoDataFrame,
        osm_waterways_data: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    catchment_boundary_lines = main_river.get_catchment_boundary_lines(catchment_area)
    osm_bound_points = get_osm_boundary_points_on_bbox(catchment_area, osm_waterways_data)
    osm_waterways_data_on_bbox = gpd.sjoin(
        osm_bound_points, catchment_boundary_lines, how='left', predicate='intersects')
    osm_waterways_data_on_bbox = osm_waterways_data_on_bbox.merge(
        catchment_boundary_lines, on='boundary_line_no', how='left').sort_index()
    osm_waterways_data_on_bbox.rename(columns={'geometry': 'boundary_line'}, inplace=True)
    osm_waterways_data_on_bbox.drop(columns=['index_right'], inplace=True)
    return osm_waterways_data_on_bbox
