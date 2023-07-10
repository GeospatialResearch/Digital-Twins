# -*- coding: utf-8 -*-
"""
@Description: Enum(s) used in the tide_slr module.
@Author: sli229
"""

from enum import StrEnum


class DatumType(StrEnum):
    """
    Enum class representing different datum types.

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
    """
    Enum class representing different types of approaches.

    Attributes
    ----------
    KING_TIDE : str
        King Tide approach.
    PERIOD_TIDE : str
        Period Tide approach.
    """
    KING_TIDE = "king_tide"
    PERIOD_TIDE = "period_tide"
