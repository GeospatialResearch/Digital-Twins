# -*- coding: utf-8 -*-
# Copyright © 2021-2026 Geospatial Research Institute Toi Hangarau
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

"""Web endpoints of mock plugin B."""

from flask import Blueprint

from .processes import WORKSPACE

blueprint = Blueprint("eddie_mock_b", __name__)


@blueprint.route("/mock-b")
def ping() -> str:
    """
    Name this plugin, to show its route is served without colliding with other plugins.

    Returns
    -------
    str
        The plugin's workspace name.
    """
    return WORKSPACE
