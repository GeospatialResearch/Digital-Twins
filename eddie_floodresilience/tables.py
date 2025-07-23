# -*- coding: utf-8 -*-
# Copyright © 2021-2025 Geospatial Research Institute Toi Hangarau
# LICENSE: https://github.com/GeospatialResearch/Digital-Twins/blob/master/LICENSE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""This script contains SQLAlchemy models for FReDT database tables and utility functions for database operations."""
from datetime import datetime, timezone

from geoalchemy2 import Geometry
from sqlalchemy import Column, Integer, String, PrimaryKeyConstraint, DateTime, Boolean

from src.digitaltwin.tables import Base


class RiverNetworkExclusions(Base):
    """
    Class representing the 'rec_network_exclusions' table.

    Attributes
    ----------
    __tablename__ : str
        Name of the database table.
    rec_network_id : int
        An identifier for the river network associated with each new run.
    objectid : int
        An identifier for the REC river object matching from the 'rec_data' table.
    exclusion_cause : str
        Cause of exclusion, i.e., the reason why the REC river geometry was excluded.
    geometry : LineString
        Geometric representation of the excluded REC river features.
    """  # pylint: disable=too-few-public-methods

    __tablename__ = "rec_network_exclusions"
    rec_network_id = Column(Integer, primary_key=True,
                            comment="An identifier for the river network associated with each run")
    objectid = Column(Integer, primary_key=True,
                      comment="An identifier for the REC river object matching from the 'rec_data' table")
    exclusion_cause = Column(String, comment="Cause of exclusion")
    geometry = Column(Geometry("LINESTRING", srid=2193))

    __table_args__ = (
        PrimaryKeyConstraint('rec_network_id', 'objectid', name='network_exclusions_pk'),
    )


class RiverNetwork(Base):
    """
    Class representing the 'rec_network' table.

    Attributes
    ----------
    __tablename__ : str
        Name of the database table.
    rec_network_id : int
        An identifier for the river network associated with each new run (primary key).
    network_path : str
        Path to the REC river network file.
    network_data_path : str
        Path to the REC river network data file for the AOI.
    created_at : datetime
        Timestamp indicating when the output was created.
    geometry : Polygon
        Geometric representation of the catchment area coverage.
    """  # pylint: disable=too-few-public-methods

    __tablename__ = "rec_network"
    rec_network_id = Column(Integer, primary_key=True,
                            comment="An identifier for the river network associated with each run")
    network_path = Column(String, comment="path to the rec river network file")
    network_data_path = Column(String, comment="path to the rec river network data file for the AOI")
    created_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc), comment="output created datetime")
    geometry = Column(Geometry("POLYGON", srid=2193))


class BGFloodModelOutput(Base):
    """
    Class representing the 'bg_flood_model_output' table.

    Attributes
    ----------
    __tablename__ : str
        Name of the database table.
    unique_id : int
        Unique identifier for each entry (primary key).
    file_name : str
        Name of the flood model output file.
    file_path : str
        Path to the flood model output file.
    created_at : datetime
        Timestamp indicating when the output was created.
    geometry : Polygon
        Geometric representation of the catchment area coverage.
    """  # pylint: disable=too-few-public-methods

    __tablename__ = "bg_flood_model_output"
    unique_id = Column(Integer, primary_key=True, autoincrement=True)
    file_name = Column(String, comment="name of the flood model output file")
    file_path = Column(String, comment="path to the flood model output file")
    created_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc), comment="output created datetime")
    geometry = Column(Geometry("POLYGON", srid=2193))


class BuildingFloodStatus(Base):
    """
    Class representing the 'building_flood_status' table.
    Represents if a building is flooded for a given flood model output

    Attributes
    ----------
    __tablename__ : str
        Name of the database table.
    unique_id : int
        Unique identifier for each entry (primary key).
    building_outline_id : int
        Foreign key building outline id matching from nz_building_outlines table
    is_flooded : bool
        If the building is flooded or not
    flood_model_id: int.
        Foreign key mathing the unique_id from bg_flood_model_output table
    """  # pylint: disable=too-few-public-methods

    __tablename__ = "building_flood_status"
    unique_id = Column(Integer, primary_key=True, autoincrement=True)
    building_outline_id = Column(Integer, comment="The building outline id matching from nz_building_outlines table")
    is_flooded = Column(Boolean, comment="If the building is flooded or not")
    flood_model_id = Column(Integer)
