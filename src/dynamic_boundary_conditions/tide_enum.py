# -*- coding: utf-8 -*-
"""
@Description: Enum(s) used in the dynamic_boundary_conditions tide module.
@Author: sli229
"""

from enum import StrEnum


class DatumType(StrEnum):
    """
    Attributes
    ----------
    LAT : str
        Lowest astronomical tide.
    MSL : str
        Mean sea level.
    """
    LAT = "lat"
    MSL = "msl"


class ApproachType(StrEnum):
    KING_TIDE = "king_tide"
    PERIOD_TIDE = "period_tide"
