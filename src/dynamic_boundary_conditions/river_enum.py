# -*- coding: utf-8 -*-
"""
@Description: Enum(s) used in the dynamic_boundary_conditions river module.
@Author: sli229
"""

from enum import StrEnum


class BoundType(StrEnum):
    """
    Attributes
    ----------
    LOWER : str
        Lower.
    MIDDLE : str
        Middle.
    UPPER : str
        Upper.
    """
    LOWER = "lower"
    MIDDLE = "middle"
    UPPER = "upper"
