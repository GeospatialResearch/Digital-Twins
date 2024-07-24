"""This script contains a SQLAlchemy model for the medusa 2.0 database table."""

from sqlalchemy import Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class MEDUSA2ModelOutput(Base):
    """
    Class representing the 'medusa_2_model_output' table.

    Attributes
    ----------
    __tablename__ : str
        Name of the database table.
    Index : int
        Unique identifier for each entry (primary key).
    SurfaceArea : float
        Surface area in meters squared of this feature.
    SurfaceType : str
        The type of surface this is. Converted to string from Enum.
    TSS : float
        Total suspended solid of the surface.
    TCu : float
        Total copper of the surface.
    TZn: float
        Total zinc of the surface.
    DCu: float
        Total dissolved copper of the surface.
    DZn: float
        Total dissolved zinc of the surface.
    scenario_id: int
        Unique identifier for the rainfall event that this feature was processed with.
    """  # pylint: disable=too-few-public-methods

    __tablename__ = "medusa2_model_output"
    Index = Column(Integer, primary_key=True)
    SurfaceArea = Column(Float)
    SurfaceType = Column(String)
    TSS = Column(Float)
    TCu = Column(Float)
    TZn = Column(Float)
    DCu = Column(Float)
    DZn = Column(Float)
    scenario_id = Column(Integer, primary_key=True)
