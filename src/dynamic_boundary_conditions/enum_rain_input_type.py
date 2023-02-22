from enum import StrEnum


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
