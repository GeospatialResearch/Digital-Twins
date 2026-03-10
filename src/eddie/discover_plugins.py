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

"""Methods used to find packages that are eddie plugins, and return information to help import them."""
import importlib
import logging
import pkgutil
from types import ModuleType

from eddie.digitaltwin.utils import setup_logging

setup_logging()
log = logging.getLogger(__name__)


def discover_plugins() -> dict[str, ModuleType]:
    """
    Collate all plugin packages that start with 'eddie_' and return their information as a dict

    Returns
    -------
    dict[str, ModuleType]
        Dictionary of all packages found in the current environment starting with 'eddie_'.
        The key is the package name, the value is the package module itself.
    """
    plugins = {
        name: importlib.import_module(name)
        for _finder, name, _is_pkg in pkgutil.iter_modules() if name.startswith('eddie_')
    }
    log.info(f"Plugins discovered: {plugins}")
    return plugins
