# -*- coding: utf-8 -*-
# Copyright © 2021-2025 Geospatial Research Institute Toi Hangarau
# LICENSE: https://github.com/GeospatialResearch/Digital-Twins/blob/master/LICENSE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Main river script used to read and store REC data in the database, fetch OSM waterways data, create a river network
and its associated data, and generate the requested river model input for BG-Flood etc.
"""

import logging
from typing import Union, Optional

import geopandas as gpd

from src import config
from src.digitaltwin import setup_environment
from src.digitaltwin.utils import LogLevel, setup_logging, get_catchment_area
from eddie_floodresilience.dynamic_boundary_conditions.river import (
    river_data_to_from_db,
    river_network_for_aoi,
    align_rec_osm,
    river_inflows,
    hydrograph,
    river_model_input
)
from eddie_floodresilience.dynamic_boundary_conditions.river.river_enum import BoundType

log = logging.getLogger(__name__)


def main(
        selected_polygon_gdf: gpd.GeoDataFrame,
        flow_length_mins: int,
        time_to_peak_mins: Union[int, float],
        maf: bool = True,
        ari: Optional[int] = None,
        bound: BoundType = BoundType.MIDDLE,
        log_level: LogLevel = LogLevel.DEBUG) -> None:
    """
    Read and store REC data in the database, fetch OSM waterways data, create a river network and its associated data,
    and generate the requested river model input for BG-Flood.

    Parameters
    ----------
    selected_polygon_gdf : gpd.GeoDataFrame
        A GeoDataFrame representing the selected polygon, i.e., the catchment area.
    flow_length_mins : int
        Duration of the river flow in minutes.
    time_to_peak_mins : Union[int, float]
        The time in minutes when flow is at its greatest (reaches maximum).
    maf : bool = True
        Set to True to obtain MAF-based scenario data or False to obtain ARI-based scenario data.
    ari : Optional[int] = None
        The Average Recurrence Interval (ARI) value. Valid options are 5, 10, 20, 50, 100, or 1000.
        Mandatory when 'maf' is set to False, and should be set to None when 'maf' is set to True.
    bound : BoundType = BoundType.MIDDLE
        Set the type of bound (estimate) for the REC river inflow scenario data.
        Valid options include: 'BoundType.LOWER', 'BoundType.MIDDLE', or 'BoundType.UPPER'.
    log_level : LogLevel = LogLevel.DEBUG
        The log level to set for the root logger. Defaults to LogLevel.DEBUG.
        The available logging levels and their corresponding numeric values are:
        - LogLevel.CRITICAL (50)
        - LogLevel.ERROR (40)
        - LogLevel.WARNING (30)
        - LogLevel.INFO (20)
        - LogLevel.DEBUG (10)
        - LogLevel.NOTSET (0)
    """
    # Set up logging with the specified log level
    setup_logging(log_level)
    # Connect to the database
    engine = setup_environment.get_database()
    # Get catchment area
    catchment_area = get_catchment_area(selected_polygon_gdf, to_crs=2193)
    # BG-Flood Model Directory
    bg_flood_dir = config.EnvVariable.FLOOD_MODEL_DIR
    # Remove any existing river model inputs in the BG-Flood directory
    river_model_input.remove_existing_river_inputs(bg_flood_dir)

    # Store REC data to the database
    river_data_to_from_db.store_rec_data_to_db(engine)
    # Get the REC river network for the catchment area
    _, rec_network_data = river_network_for_aoi.get_rec_river_network(engine, catchment_area)

    try:
        # Obtain REC river inflow data along with the corresponding river input points used in the BG-Flood model
        rec_inflows_data = river_inflows.get_rec_inflows_with_input_points(
            engine, catchment_area, rec_network_data, distance_m=300)

        # Generate hydrograph data for the requested REC river scenario
        hydrograph_data = hydrograph.get_hydrograph_data(
            rec_inflows_data,
            flow_length_mins=flow_length_mins,
            time_to_peak_mins=time_to_peak_mins,
            maf=maf,
            ari=ari,
            bound=bound
        )

        # Generate river model inputs for BG-Flood
        river_model_input.generate_river_model_input(bg_flood_dir, hydrograph_data)

    except align_rec_osm.NoRiverDataException as error:
        # Log an info message to indicate the absence of river data
        log.info(error)


if __name__ == "__main__":
    sample_polygon = gpd.GeoDataFrame.from_file("selected_polygon.geojson")
    main(
        selected_polygon_gdf=sample_polygon,
        flow_length_mins=2880,
        time_to_peak_mins=1440,
        maf=True,
        ari=None,
        bound=BoundType.MIDDLE,
        log_level=LogLevel.DEBUG
    )
