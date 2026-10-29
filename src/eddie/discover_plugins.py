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

"""Find installed EDDIE plugins and their optional contributions, see the "Writing a plugin" wiki page."""
import importlib
from importlib.metadata import entry_points
import logging
import pkgutil
from types import ModuleType

log = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "eddie.plugins"


def discover_plugins() -> dict[str, ModuleType]:
    """
    Import every installed EDDIE plugin.
    Plugins are declared under the "eddie.plugins" entry point group.
    Packages named 'eddie_*' without an entry point are still found, but this is deprecated.

    Returns
    -------
    dict[str, ModuleType]
        The key is the plugin's import name (e.g. 'eddie_otakaro'), the value is the imported plugin module.

    Raises
    ------
    RuntimeError
        If two entry points share a plugin name but point to different modules.
    """
    # 1. Collect plugins declared under the entry point group, rejecting two modules that claim the same name
    module_names: dict[str, str] = {}  # entry point name -> module name
    for entry_point in entry_points(group=ENTRY_POINT_GROUP):
        previous = module_names.setdefault(entry_point.name, entry_point.module)
        if previous != entry_point.module:
            raise RuntimeError(f"Duplicate EDDIE plugin name {entry_point.name!r}: "
                               f"provided by both {previous!r} and {entry_point.module!r}")
    found = set(module_names.values())
    # 2. Also collect 'eddie_*' packages that have no entry point, with a deprecation warning
    for module_info in pkgutil.iter_modules():
        if module_info.name.startswith("eddie_") and module_info.name not in found:
            message = (f"Plugin {module_info.name!r} was found only by its 'eddie_' prefix, which is deprecated. "
                       f"Declare it under [project.entry-points.\"{ENTRY_POINT_GROUP}\"] in its pyproject.toml.")
            log.warning(message)
            found.add(module_info.name)
            # 3. Import every plugin found, in a stable (alphabetical) order
    plugins = {name: importlib.import_module(name) for name in sorted(found)}
    log.info(f"Plugins discovered: {plugins}")
    return plugins


def plugin_contribution(plugin: ModuleType, name: str) -> object:
    """
    Get an optional plugin contribution, from the plugin's attribute or else its submodule of that name.

    Parameters
    ----------
    plugin : ModuleType
        The plugin module, as returned by discover_plugins.
    name : str
        The contribution name, e.g. "blueprint" or "tasks".

    Returns
    -------
    object
        The attribute or submodule, or None if the plugin does not provide it.

    Raises
    ------
    ModuleNotFoundError
        If the submodule exists but itself imports a module that is missing.
    """
    if not hasattr(plugin, name):
        try:
            importlib.import_module(f"{plugin.__name__}.{name}")  # importing sets the attribute on the package
        except ModuleNotFoundError as e:
            if e.name != f"{plugin.__name__}.{name}":
                raise
    return getattr(plugin, name, None)
