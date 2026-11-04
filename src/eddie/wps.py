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

"""
Core PyWPS service. Owns the single `/wps` endpoint for the whole instance,
built by collecting each plugin's `processes` contribution.

Plugins must NOT build their own `pywps.Service` or define a `/wps` route - core owns that so that
co-hosting two WPS plugins in one instance does not collide.
A plugin contributes processes by exposing a `processes` attribute (or`<plugin>.processes` submodule) that is a
list of `pywps.Process` instances, whose `.identifier` is the plugin-local name (e.g. "medusa").
This module namespaces it to "<plugin>.<identifier>" (e.g. "otakaro.medusa") before registering it with PyWPS.
That namespaced identifier is also used as the cache `process_id` (see `eddie.digitaltwin.caching.cache_common`),
so it is stable and must not be changed once a plugin has cached results under it.
"""

import logging

import pywps

from eddie.config import EnvVariable
from eddie.digitaltwin.caching.cache_common import register_spatial_containment
from eddie.discover_plugins import discover_plugins, plugin_contribution

log = logging.getLogger(__name__)

PLUGIN_MODULE_PREFIX = "eddie_"


def _plugin_short_name(module_name: str) -> str:
    """
    Derive the namespace used for a plugin's process identifiers from its import name,
    e.g. 'eddie_otakaro' -> 'otakaro'. Modules without the deprecated 'eddie_' prefix
    are used as-is.

    Parameters
    ----------
    module_name : str
        The plugin's import name, as returned by `discover_plugins`.

    Returns
    -------
    str
        The short namespace to prefix process identifiers with.
    """
    if module_name.startswith(PLUGIN_MODULE_PREFIX):
        return module_name[len(PLUGIN_MODULE_PREFIX):]
    return module_name


def build_processes() -> list[pywps.Process]:
    """
    Collect and namespace every process contributed by every discovered plugin.
    Also registers, with the cache layer, any process that declares itself eligible for spatial-containment cache reuse
    (`process.supports_spatial_containment = True` on the `pywps.Process` instance) - this replaces a hardcoded global
    allow-list, since whether containment reuse is scientifically valid is a property of the process itself,
     not something the cache infrastructure can assume.

    Returns
    -------
    list[pywps.Process]
        `pywps.Process` instances with identifiers rewritten to '<plugin_short_name>.<original_identifier>'.

    Raises
    ------
    RuntimeError
        If two plugins/processes resolve to the same namespaced identifier.
    """
    namespaced_processes = []
    seen_identifiers: set[str] = set()

    for module_name, plugin in discover_plugins().items():
        plugin_processes = plugin_contribution(plugin, "processes") or []
        short_name = _plugin_short_name(module_name)

        for process in plugin_processes:
            namespaced_id = f"{short_name}.{process.identifier}"
            if namespaced_id in seen_identifiers:
                raise RuntimeError(f"Duplicate WPS process identifier {namespaced_id!r}")
            seen_identifiers.add(namespaced_id)

            process.identifier = namespaced_id
            if getattr(process, "supports_spatial_containment", False):
                register_spatial_containment(namespaced_id)

            namespaced_processes.append(process)
            log.info("Registered WPS process: %s (from %s)", namespaced_id, module_name)

    return namespaced_processes


def build_service() -> pywps.Service:
    """
    Build the single core `pywps.Service`, from every discovered plugin's processes.
    This is the only `pywps.Service` instance for the whole application; it is mounted
    at '/wps' by the Flask app (see `eddie.app`).

    Returns
    -------
    pywps.Service
        The configured PyWPS service, ready to be mounted as a WSGI app at '/wps'.
    """
    log.info("EDDIE_INSTANCE_TITLE=%s - building core WPS service", EnvVariable.EDDIE_INSTANCE_TITLE)
    return pywps.Service(processes=build_processes(), cfgfiles=["pywps.cfg"])
