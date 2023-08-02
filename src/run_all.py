import logging

import geopandas as gpd

from src.digitaltwin.utils import setup_logging
from src.digitaltwin import run
from src.lidar import lidar_metadata_in_db, dem_metadata_in_db
from src.dynamic_boundary_conditions import main_rainfall, main_tide_slr, main_river
from src.flood_model import bg_flood_model


def main():
    setup_logging(log_level=logging.DEBUG)
    selected_polygon_gdf = gpd.GeoDataFrame.from_file("selected_polygon.geojson")
    run.main(selected_polygon_gdf)
    lidar_metadata_in_db.main(selected_polygon_gdf)
    dem_metadata_in_db.main(selected_polygon_gdf)
    main_rainfall.main(selected_polygon_gdf)
    main_tide_slr.main(selected_polygon_gdf)
    main_river.main(selected_polygon_gdf)
    bg_flood_model.main(selected_polygon_gdf)


if __name__ == '__main__':
    main()
