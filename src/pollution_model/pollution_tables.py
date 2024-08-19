"""This script contains a SQLAlchemy model for the medusa 2.0 database table."""
import abc

from sqlalchemy import Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import DeclarativeMeta


class _DeclarativeABCMeta(DeclarativeMeta, abc.ABCMeta):
    """Metaclass to allow abstract base class to be used with a declarative base."""


Base = declarative_base(metaclass=_DeclarativeABCMeta)


class _BaseMedusa2ModelOutput(Base):
    """
    Abstract Base Class (abc) representing each of 'medusa_2_model_output' tables.

    Attributes
    ----------
    __tablename__ : str
       Name of the database table.
    scenario_id : int
       The rainfall event scenario ID this feature was processed with, makes up part of the primary key.
    spatial_feature_id: int
       The id of the spatial feature this row is associated with, makes up part of the primary key.
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
    """

    __abstract__ = True  # This is an abstract base class

    @property
    @abc.abstractmethod
    def __tablename__(self) -> str:
        """This must be overridden in the child class. e.g. __tablename__ = "medusa2_model_output_buildings."""
        raise NotImplementedError("__tablename__ must be overidden in the child class."
                                  "e.g. __tablename__ = \"medusa2_model_output_buildings.\"")

    @property
    @abc.abstractmethod
    def spatial_feature_id(self) -> Column:
        """This must be overridden in the child class. e.g. __tablename__ = "medusa2_model_output_buildings"."""
        raise NotImplementedError("spatial_feature_id must be overridden in the child class."
                                  "Eg. spatial_feature_id = Column(Integer, primary_key=True, name=\"building_id\")")

    @property
    @abc.abstractmethod
    def geometry_table(self) -> Column:
        """This must be overridden in the child class. e.g. geometry_table = "nz_buildings"."""
        raise NotImplementedError("geometry_table must be overridden in the child class."
                                  "Eg. geometry_table = \"nz_buildings\"")

    scenario_id = Column(Integer, primary_key=True)
    surface_type = Column(String, nullable=False)
    total_suspended_solids = Column(Float, nullable=False)
    total_copper = Column(Float, nullable=False)
    total_zinc = Column(Float, nullable=False)
    dissolved_copper = Column(Float, nullable=False)
    dissolved_zinc = Column(Float, nullable=False)


class Medusa2ModelOutputBuildings(_BaseMedusa2ModelOutput):
    """Class representing the medusa2_model_output_buildings table."""  # pylint: disable=too-few-public-methods

    __tablename__ = "medusa2_model_output_buildings"
    spatial_feature_id = Column(Integer, primary_key=True, name="building_id")
    geometry_table = "nz_building_outlines"


class Medusa2ModelOutputRoads(_BaseMedusa2ModelOutput):
    """Class representing the medusa2_model_output_roads table."""  # pylint: disable=too-few-public-methods

    __tablename__ = "medusa2_model_output_roads"
    spatial_feature_id = Column(Integer, primary_key=True, name="road_id")
    geometry_table = "nz_roads"
