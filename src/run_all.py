# -*- coding: utf-8 -*-
"""This script runs each module in the Digital Twin using a Sample Polygon."""

from enum import Enum
from types import ModuleType
from typing import Dict, Union

import geopandas as gpd
import shapely

from src.digitaltwin.utils import LogLevel
from floodresilience import retrieve_static_boundaries
from floodresilience.dynamic_boundary_conditions.rainfall import main_rainfall
from floodresilience.dynamic_boundary_conditions.rainfall.rainfall_enum import RainInputType, HyetoMethod
from floodresilience.dynamic_boundary_conditions.river import main_river
from floodresilience.dynamic_boundary_conditions.river.river_enum import BoundType
from floodresilience.dynamic_boundary_conditions.tide import main_tide_slr
from floodresilience.flood_model import bg_flood_model, process_hydro_dem
from otakaro.pollution_model import run_medusa_2
from otakaro.environmental.water_quality import main_water_quality


def main(
        selected_polygon_gdf: gpd.GeoDataFrame,
        modules_to_parameters: Dict[ModuleType, Dict[str, Union[str, int, float, bool, None, Enum]]]) -> None:
    """
    Run each module in the Digital Twin using the selected polygon and the defined parameters for each module's
    main function.

    Parameters
    ----------
    selected_polygon_gdf : gpd.GeoDataFrame
        A GeoDataFrame representing the selected polygon, i.e., the catchment area.
    modules_to_parameters : Dict[ModuleType, Dict[str, Union[str, int, float, bool, None, Enum]]]
        A dictionary that associates each module with the parameters necessary for its main function, including the
        option to set the log level for each module's root logger.
        The available logging levels and their corresponding numeric values are:
        - LogLevel.CRITICAL (50)
        - LogLevel.ERROR (40)
        - LogLevel.WARNING (30)
        - LogLevel.INFO (20)
        - LogLevel.DEBUG (10)
        - LogLevel.NOTSET (0)
    """
    # Iterate through the dictionary containing modules and their parameters
    for module, parameters in modules_to_parameters.items():
        # Call the main function of each module with the selected polygon and specified parameters
        module.main(selected_polygon_gdf, **parameters)


DEFAULT_MODULES_TO_PARAMETERS = {
    retrieve_static_boundaries: {
        "log_level": LogLevel.INFO
    },
    process_hydro_dem: {
        "log_level": LogLevel.INFO
    },
    main_rainfall: {
        "rcp": 2.6,
        "time_period": "2031-2050",
        "ari": 100,
        "storm_length_mins": 2880,
        "time_to_peak_mins": 1440,
        "increment_mins": 10,
        "hyeto_method": HyetoMethod.ALT_BLOCK,
        "input_type": RainInputType.UNIFORM,
        "log_level": LogLevel.INFO
    },
    main_tide_slr: {
        "tide_length_mins": 2880,
        "time_to_peak_mins": 1440,
        "interval_mins": 10,
        "proj_year": 2030,
        "confidence_level": "low",
        "ssp_scenario": "SSP1-2.6",
        "add_vlm": False,
        "percentile": 50,
        "log_level": LogLevel.INFO
    },
    main_river: {
        "flow_length_mins": 2880,
        "time_to_peak_mins": 1440,
        "maf": True,
        "ari": None,
        "bound": BoundType.MIDDLE,
        "log_level": LogLevel.INFO
    },
    bg_flood_model: {
        "output_timestep": 1,
        "end_time": 2,
        "resolution": None,
        "mask": 9999,
        "gpu_device": -1,
        "small_nc": 0,
        "log_level": LogLevel.INFO
    },
    run_medusa_2: {
        "log_level": LogLevel.INFO,
        "antecedent_dry_days": 1,
        "average_rain_intensity": 1,
        "event_duration": 1,
        # rainfall pH assumed for all of NZ is 6.5
        "rainfall_ph": 6.5
    },
    main_water_quality: {
        "log_level": LogLevel.INFO
    }
}


if __name__ == '__main__':
    # Read the area of interst file in
    aoi = gpd.read_file("selected_polygon.geojson")
    # Convert to WGS84 to deliberately introduce rounding errors. Ensures our development acts like production.
    # These rounding errors occur in production when serialising WGS84 polygons
    aoi = aoi.to_crs(4326)

    # Convert the polygon back to 2193 crs, and recalculate the bounds to ensure it is a rectangle.
    bbox_2193 = aoi.to_crs(2193).bounds.rename(columns={"minx": "xmin", "maxx": "xmax", "miny": "ymin", "maxy": "ymax"})
    # Create sample polygon from bounding box
    sample_polygon = gpd.GeoDataFrame(index=[0], crs="epsg:2193", geometry=[shapely.box(**bbox_2193.iloc[0])])

    # Run all modules with sample polygon that intentionally contains slight rounding errors.
    main(sample_polygon, DEFAULT_MODULES_TO_PARAMETERS)
