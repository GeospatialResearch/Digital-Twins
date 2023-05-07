import logging
import geopandas as gpd

from src.digitaltwin import get_data_from_db, run
from src.dynamic_boundary_conditions import main_rainfall
from src.lidar import lidar_metadata_in_db
from src.flood_model import bg_flood_model

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(levelname)s:%(asctime)s:%(name)s:%(message)s")
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
log.addHandler(stream_handler)

if __name__ == '__main__':
    selected_polygon_gdf = gpd.GeoDataFrame.from_file("selected_polygon.geojson")
    log.debug("run.main()")
    run.main()
    log.debug("get_data_from_db.main()")
    get_data_from_db.main(selected_polygon_gdf)
    log.debug("lidar_metadata_in_db.main()")
    lidar_metadata_in_db.main(selected_polygon_gdf)
    log.debug("main_rainfall.main()")
    main_rainfall.main(selected_polygon_gdf)
    log.debug("bg_flood_model.main()")
    bg_flood_model.main(selected_polygon_gdf)
