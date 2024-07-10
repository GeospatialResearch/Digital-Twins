# -*- coding: utf-8 -*-
"""Enum(s) used in the rainfall module."""

from enum import StrEnum


class HyetoMethod(StrEnum):
    """
    Enum class representing different hyetograph methods.

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
    Enum class representing different types of rain input used in the BG-Flood Model.

    Attributes
    ----------
    UNIFORM : str
        Spatially uniform rain input.
    VARYING : str
        Spatially varying rain input.
    """

    UNIFORM = "uniform"
    VARYING = "varying"
