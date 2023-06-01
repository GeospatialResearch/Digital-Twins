import logging

import geopandas as gpd

from src.digitaltwin import get_data_from_db, run
from src.lidar import lidar_metadata_in_db
from src.dynamic_boundary_conditions import main_rainfall, main_tide_slr, main_river
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
    get_data_from_db.main()
    log.debug("lidar_metadata_in_db.main()")
    lidar_metadata_in_db.main()
    log.debug("main_rainfall.main()")
    main_rainfall.main()
    log.debug("main_tide_slr.main()")
    main_tide_slr.main()
    log.debug("main_river.main()")
    main_river.main(selected_polygon_gdf)
    log.debug("bg_flood_model.main()")
    bg_flood_model.main()
