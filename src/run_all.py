import logging

import geopandas as gpd

from src.digitaltwin.utils import setup_logging
from src.digitaltwin import run
from src.lidar import lidar_metadata_in_db, dem_metadata_in_db
from src.dynamic_boundary_conditions import main_rainfall, main_tide_slr, main_river
from src.flood_model import bg_flood_model

log = logging.getLogger(__name__)


if __name__ == '__main__':
    setup_logging(log_level=logging.DEBUG)
    selected_polygon_gdf = gpd.GeoDataFrame.from_file("selected_polygon.geojson")
    log.info("run.main()")
    run.main(selected_polygon_gdf)
    log.info("lidar_metadata_in_db.main()")
    lidar_metadata_in_db.main(selected_polygon_gdf)
    log.info("dem_metadata_in_db.py")
    dem_metadata_in_db.main(selected_polygon_gdf)
    log.info("main_rainfall.main()")
    main_rainfall.main(selected_polygon_gdf)
    log.info("main_tide_slr.main()")
    main_tide_slr.main(selected_polygon_gdf)
    log.info("main_river.main()")
    main_river.main(selected_polygon_gdf)
    log.info("bg_flood_model.main()")
    bg_flood_model.main(selected_polygon_gdf)
