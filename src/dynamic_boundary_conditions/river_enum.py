# -*- coding: utf-8 -*-
"""
@Description: Enum(s) used in the river module.
@Author: sli229
"""

from enum import StrEnum


class BoundType(StrEnum):
    """
    Enum class representing different types of estimates used in river flow scenarios.

    Attributes
    ----------
    LOWER : str
        Lower bound of a confidence interval.
    MIDDLE : str
        Point estimate or sample mean.
    UPPER : str
        Upper bound of a confidence interval.
    """
    LOWER = "lower"
    MIDDLE = "middle"
    UPPER = "upper"
