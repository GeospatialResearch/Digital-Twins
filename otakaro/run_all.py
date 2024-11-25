# -*- coding: utf-8 -*-
"""This script runs each module in the Digital Twin using a Sample Polygon."""

from src.digitaltwin.utils import LogLevel
from src.run_all import create_sample_polygon, main
from otakaro import initialise_db_with_files
from otakaro.pollution_model import run_medusa_2
from otakaro.environmental.water_quality import main_water_quality

DEFAULT_MODULES_TO_PARAMETERS = {
    initialise_db_with_files: {
        "log_level": LogLevel.INFO,
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
    sample_polygon = create_sample_polygon()
    # Run all modules with sample polygon that intentionally contains slight rounding errors.
    main(sample_polygon, DEFAULT_MODULES_TO_PARAMETERS)
