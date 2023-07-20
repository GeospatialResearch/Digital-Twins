import pathlib

import geopandas as gpd
from shapely.geometry import LineString

from src import config
from src.digitaltwin import setup_environment
from src.digitaltwin.utils import get_catchment_area
from src.dynamic_boundary_conditions.river_enum import BoundType
from src.dynamic_boundary_conditions import (
    river_data_to_from_db,
    river_network_for_aoi,
    osm_waterways,
    river_osm_combine,
    hydrograph,
    river_model_input
)


def get_catchment_boundary_lines(catchment_area: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    catchment_polygon = catchment_area["geometry"].iloc[0]
    # Create an empty list to store the individual boundary line segments
    boundary_lines = []
    # Extract the exterior (outer boundary) of the polygon
    exterior = catchment_polygon.exterior
    # Iterate over the coordinates of the exterior boundary
    for i in range(len(exterior.coords) - 1):
        # Create a LineString using two consecutive coordinates
        line_segment = LineString([exterior.coords[i], exterior.coords[i + 1]])
        # Append the line segment to the list of boundary lines
        boundary_lines.append(line_segment)
    # Create a GeoDataFrame from the list of boundary lines
    catchment_boundary_lines = gpd.GeoDataFrame(geometry=boundary_lines, crs=catchment_area.crs).reset_index(drop=True)
    catchment_boundary_lines['boundary_line_no'] = catchment_boundary_lines.index + 1
    return catchment_boundary_lines


def remove_existing_river_inputs(bg_flood_dir: pathlib.Path) -> None:
    # iterate through all files in the directory
    for file_path in bg_flood_dir.glob('river[0-9]*.txt'):
        # remove the file
        file_path.unlink()


def main(selected_polygon_gdf: gpd.GeoDataFrame) -> None:
    # Connect to the database
    engine = setup_environment.get_database()
    # Get catchment area
    catchment_area = get_catchment_area(selected_polygon_gdf, to_crs=2193)
    # BG-Flood Model Directory
    bg_flood_dir = config.get_env_variable("FLOOD_MODEL_DIR", cast_to=pathlib.Path)
    # Remove existing river model input files
    remove_existing_river_inputs(bg_flood_dir)

    # Store REC1 data to the database
    river_data_to_from_db.store_rec1_data_to_db(engine)
    # Get REC1 data from the database for the catchment area
    rec1_data = river_data_to_from_db.get_rec1_data_from_db(engine, catchment_area)

    # Create a river network for the catchment area using the REC1 data
    rec1_network_data = river_network_for_aoi.create_rec1_network_data(rec1_data)
    # rec1_network = river_network_for_aoi.build_rec1_network(rec1_network_data)
    # Obtain the REC1 network data that corresponds to the points of intersection on the catchment area boundary
    rec1_network_data_on_bbox = river_network_for_aoi.get_rec1_network_data_on_bbox(catchment_area, rec1_network_data)

    # Fetch OSM waterways data for the catchment area
    osm_waterways_data = osm_waterways.get_osm_waterways_data(catchment_area)
    # Obtain the OSM waterways data that corresponds to the points of intersection on the catchment area boundary
    osm_waterways_data_on_bbox = osm_waterways.get_osm_waterways_data_on_bbox(catchment_area, osm_waterways_data)

    # Find the closest OSM waterway to each REC1 river and determine the target points used for the model input
    matched_data = river_osm_combine.get_matched_data_with_target_locations(
        engine, catchment_area, rec1_network_data_on_bbox, osm_waterways_data_on_bbox, distance_m=300)

    # Get hydrograph data
    hydrograph_data = hydrograph.get_hydrograph_data(
        matched_data,
        river_length_mins=2880,
        time_to_peak_mins=1440,
        maf=True,
        ari=None,
        bound=BoundType.MIDDLE)

    # Generate river model inputs for BG-Flood
    river_model_input.generate_river_model_input(bg_flood_dir, hydrograph_data)


if __name__ == "__main__":
    sample_polygon = gpd.GeoDataFrame.from_file("selected_polygon.geojson")
    main(sample_polygon)
