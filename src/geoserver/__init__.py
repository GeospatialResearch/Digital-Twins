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

"""
Functions and utilities for loading and serving data with geoserver.
Imports here are accessible directly by `from src import geoserver`.
"""
from .database_layers import create_datastore_layer, create_db_store_if_not_exists
from .geoserver_common import create_workspace_if_not_exists
from .netcdf_layers import add_nc_to_geoserver
from .raster_layers import add_gtiff_to_geoserver

__all__ = [
    "add_gtiff_to_geoserver",
    "add_nc_to_geoserver",
    "create_datastore_layer",
    "create_db_store_if_not_exists",
    "create_workspace_if_not_exists",
]
