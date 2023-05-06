# -*- coding: utf-8 -*-
"""
@Description: Enum(s) used in the dynamic_boundary_conditions rainfall module.
@Author: sli229
"""

from enum import StrEnum


class HyetoMethod(StrEnum):
    """
    Attributes
    ----------
    ALT_BLOCK : str
        Alternating Block Method.
    CHICAGO : str
        Chicago Method.
    """
    ALT_BLOCK = "alt_block"
    CHICAGO = "chicago"


class RainInputType(StrEnum):
    """
    Attributes
    ----------
    UNIFORM : str
        Spatially uniform rain input.
    VARYING : str
        Spatially varying rain input.
    """
    UNIFORM = "uniform"
    VARYING = "varying"
