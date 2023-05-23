from typing import Dict

import geopandas as gpd
from shapely.geometry import Point
import networkx as nx

from src.digitaltwin import setup_environment
from src.dynamic_boundary_conditions import main_river, river_data_to_from_db


def add_first_last_coords_to_rec1(rec1_data: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    # Create a copy of the input dataframe
    rec1_data_w_node_coords = rec1_data.copy()
    # Create columns for the first and last coordinates of each LineString
    rec1_data_w_node_coords["first_coord"] = rec1_data_w_node_coords["geometry"].apply(lambda g: Point(g.coords[0]))
    rec1_data_w_node_coords["last_coord"] = rec1_data_w_node_coords["geometry"].apply(lambda g: Point(g.coords[-1]))
    return rec1_data_w_node_coords


def get_unique_nodes_dict(rec1_data_w_node_coords: gpd.GeoDataFrame) -> Dict[Point, int]:
    # Get all unique coordinates from the first and last coordinate columns
    rec1_node_coords = (
            rec1_data_w_node_coords["first_coord"].to_list() +
            rec1_data_w_node_coords["last_coord"].to_list()
    )
    unique_node_coords = [x for i, x in enumerate(rec1_node_coords) if x not in rec1_node_coords[:i]]
    # Create a dictionary mapping each unique coordinate to a node number
    unique_nodes_dict = {coord_point: i for i, coord_point in enumerate(unique_node_coords)}
    return unique_nodes_dict


def create_rec1_network_data_for_aoi(rec1_data: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    rec1_network_data = add_first_last_coords_to_rec1(rec1_data)
    unique_nodes_dict = get_unique_nodes_dict(rec1_network_data)
    # Create columns for the first and last node numbers
    rec1_network_data["first_node"] = rec1_network_data["first_coord"].apply(lambda x: unique_nodes_dict.get(x, None))
    rec1_network_data["last_node"] = rec1_network_data["last_coord"].apply(lambda x: unique_nodes_dict.get(x, None))
    return rec1_network_data


def build_rec1_network_for_aoi(rec1_network_data: gpd.GeoDataFrame) -> nx.Graph:
    rec1_network = nx.Graph()
    for _, row in rec1_network_data.iterrows():
        rec1_network.add_nodes_from([(row["first_node"], {"geom": row["first_coord"]})])
        rec1_network.add_nodes_from([(row["last_node"], {"geom": row["last_coord"]})])
        rec1_network.add_edge(
            row["first_node"],
            row["last_node"],
            objectid=row["objectid"],
            nzreach=row["nzreach"],
            areakm2=row["areakm2"],
            strm_order=row["strm_order"],
            geometry=row["geometry"])
    return rec1_network


def get_rec1_boundary_points_on_bbox(
        catchment_area: gpd.GeoDataFrame,
        rec1_network_data: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    catchment_boundary = catchment_area.exterior.iloc[0]
    rec1_bound_points_on_bbox = (
        rec1_network_data[rec1_network_data.intersects(catchment_boundary)].reset_index(drop=True))
    rec1_bound_points = []
    for _, row in rec1_bound_points_on_bbox.iterrows():
        geometry = row["geometry"]
        boundary_point = catchment_boundary.intersection(geometry) if catchment_boundary.intersects(geometry) else None
        rec1_bound_points.append(boundary_point)
    rec1_bound_points_on_bbox["boundary_point"] = gpd.GeoSeries(
        rec1_bound_points, crs=rec1_bound_points_on_bbox["geometry"].crs)
    rec1_bound_points_on_bbox["boundary_point_centre"] = rec1_bound_points_on_bbox["boundary_point"].centroid
    rec1_bound_points_on_bbox = rec1_bound_points_on_bbox.set_geometry("boundary_point_centre")
    rec1_bound_points_on_bbox.rename(columns={'geometry': 'rec1_river_line'}, inplace=True)
    return rec1_bound_points_on_bbox


def get_rec1_network_data_on_bbox(
        catchment_area: gpd.GeoDataFrame,
        rec1_network_data: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    catchment_boundary_lines = main_river.get_catchment_boundary_lines(catchment_area)
    rec1_bound_points = get_rec1_boundary_points_on_bbox(catchment_area, rec1_network_data)
    rec1_network_data_on_bbox = gpd.sjoin(
        rec1_bound_points, catchment_boundary_lines, how='left', predicate='intersects')
    rec1_network_data_on_bbox = rec1_network_data_on_bbox.merge(
        catchment_boundary_lines, on='boundary_line_no', how='left').sort_index()
    rec1_network_data_on_bbox.rename(columns={'geometry': 'boundary_line'}, inplace=True)
    rec1_network_data_on_bbox.drop(columns=['index_right'], inplace=True)
    return rec1_network_data_on_bbox


def main():
    # Connect to the database
    engine = setup_environment.get_database()
    # Get catchment area
    catchment_area = main_river.get_catchment_area(r"selected_polygon.geojson")

    # --- river_data_to_from_db.py -------------------------------------------------------------------------------------
    # Store REC1 data to db
    rec1_data_dir = "U:/Research/FloodRiskResearch/DigitalTwin/stored_data/rec1_data"
    river_data_to_from_db.store_rec1_data_to_db(engine, rec1_data_dir)
    # Store sea-draining catchments data to db
    river_data_to_from_db.store_sea_drain_catchments_to_db(engine, layer_id=99776)
    # Get REC1 data from db covering area of interest
    rec1_data = river_data_to_from_db.get_rec1_data_from_db(engine, catchment_area)

    # --- river_network_for_aoi.py -------------------------------------------------------------------------------------
    # Create REC1 network covering area of interest
    rec1_network_data = create_rec1_network_data_for_aoi(rec1_data)
    rec1_network = build_rec1_network_for_aoi(rec1_network_data)
    # Get REC1 boundary points crossing the catchment boundary
    rec1_network_data_on_bbox = get_rec1_network_data_on_bbox(catchment_area, rec1_network_data)
    print(rec1_network_data_on_bbox)


if __name__ == "__main__":
    main()
