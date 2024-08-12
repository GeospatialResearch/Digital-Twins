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
    scenario_id : int
        The rainfall event scenario ID this feature was processed with, makes up part of the primary key.
    spatial_feature_id: int
        The id of the spatial feature this row is associated with, makes up part of the primary key.
    surface_area : float
        Surface area in meters squared of this feature.
    surface_type : str
        The type of surface this is. Converted to string from Enum.
    total_suspended_solids : float
        Total suspended solids of the surface.
    total_copper : float
        Total copper of the surface.
    total_zinc: float
        Total zinc of the surface.
    dissolved_copper float
        Total dissolved copper of the surface.
    dissolved_zinc: float
        Total dissolved zinc of the surface.
    """  # pylint: disable=too-few-public-methods

    __tablename__ = "medusa2_model_output"
    scenario_id = Column(Integer, primary_key=True)
    spatial_feature_id = Column(Integer, primary_key=True)
    surface_area = Column(Float, nullable=False)
    surface_type = Column(String, nullable=False)
    total_suspended_solids = Column(Float, nullable=False)
    total_copper = Column(Float, nullable=False)
    total_zinc = Column(Float, nullable=False)
    dissolved_copper = Column(Float, nullable=False)
    dissolved_zinc = Column(Float, nullable=False)
