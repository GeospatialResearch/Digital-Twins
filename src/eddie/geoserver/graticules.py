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
Helpers for publishing a graticules (lat/lon grid) layer to GeoServer.

A graticules layer is backed by GeoServer's "Graticule" community extension.
"""

from http import HTTPStatus
from importlib import resources
import logging
import requests

from eddie.config import EnvVariable
from eddie.geoserver.geoserver_common import (
    create_workspace_if_not_exists, does_resource_exist, force_config_refresh, get_data_store_url,
    get_workspace_url
)

log = logging.getLogger(__name__)
_xml_header = {"Content-type": "text/xml"}

#: The default name for a graticule data store
DEFAULT_GRATICULE_NAME = "Graticule_15"
#: The default graticule line spacings, in degrees, that the data store will generate.
DEFAULT_GRATICULE_STEPS: tuple[int | float, ...] = (15,)
#: The name of the folder that graticule templates are stored in, for use with importlib.resources
GRATICULE_TEMPLATES_RESOURCE_MODULE = f"{__package__}.templates.graticule"


def create_graticules_layer(
    workspace_name: str,
    data_store_name: str = DEFAULT_GRATICULE_NAME,
    layer_name: str = DEFAULT_GRATICULE_NAME,
    steps: list[int | float] | tuple[int | float] = DEFAULT_GRATICULE_STEPS
) -> None:
    """
    Create a graticules (lat/lon grid) layer in GeoServer, creating its backing data store first if needed.

    Safe to repeat: if the layer already exists, this function returns without making any changes.

    Parameters
    ----------
    workspace_name : str
        The name of the GeoServer workspace to create the layer in.
    data_store_name : str
        The name of the graticules data store that will back the layer. Defaults to DEFAULT_GRATICULE_NAME.
    layer_name : str
        The name to give the created layer. Defaults to DEFAULT_GRATICULE_NAME.
    steps : list[int | float] | tuple[int | float]
        The graticule line spacings, in degrees, that the data store will generate (e.g. [15] for lines every
        15 degrees). Defaults to DEFAULT_GRATICULE_STEPS.
    """
    # Ensure the data store this layer will be served from exists before configuring the layer itself.
    create_data_store_for_graticules_layer_if_not_exists(workspace_name, data_store_name, steps)
    log.info(f"Creating graticules layer '{layer_name}'.")
    layer_url = f"{get_data_store_url(workspace_name, data_store_name)}/featuretypes/{layer_name}"
    if does_resource_exist(layer_url):
        log.debug(f"Layer '{layer_name}' already exists.")
        return

    # GeoServer's data-directory layout expects each layer's configuration files to live in their own directory,
    # nested under the workspace and data store. Create it manually so later writes have somewhere to go.
    layer_directory = EnvVariable.DATA_DIR_GEOSERVER / "workspaces" / workspace_name / data_store_name / layer_name
    layer_directory.mkdir(parents=True, exist_ok=True)

    # Construct the feature type payload from its template.
    featuretype_template = resources.read_text(
        GRATICULE_TEMPLATES_RESOURCE_MODULE,
        "graticule_featuretype_template.xml"
    )
    # steps_range is a human-readable label describing the configured spacings (e.g. "5_15" for multiple steps,
    # or "15" for a single step), used to name the feature type distinctly from other graticule layers.
    if len(steps) > 1:
        steps_range = f"{min(steps)}_{max(steps)}"
    elif len(steps) == 1:
        steps_range = str(steps[0])
    else:
        steps_range = ""
    featuretype_payload = featuretype_template.format(
        workspace_name=workspace_name, data_store_name=data_store_name, layer_name=layer_name, steps_range=steps_range
    )
    # Write directly to GeoServer's data directory rather than posting to the REST API, because the Graticule
    # store type is configured as static files on disk rather than through the usual featuretypes REST endpoint.
    encoding = "utf-8"
    with open(layer_directory / "featuretype.xml", "w", encoding=encoding) as f:
        f.write(featuretype_payload)

    # Construct the layer payload from its template, in the same way as the feature type above.
    layer_template = resources.read_text(
        GRATICULE_TEMPLATES_RESOURCE_MODULE,
        "graticule_layer_template.xml"
    )
    layer_payload = layer_template.format(
        workspace_name=workspace_name, layer_name=layer_name
    )
    with open(layer_directory / "layer.xml", "w", encoding=encoding) as f:
        f.write(layer_payload)
    # The feature type and layer were written directly to disk rather than via the REST API, so GeoServer will
    # not know about them until its configuration is reloaded.
    force_config_refresh()


def create_data_store_for_graticules_layer_if_not_exists(
    workspace_name: str,
    data_store_name: str,
    steps: list[int | float]
) -> None:
    """
    Create a GeoServer Graticule data store, configured to generate grid lines at the given spacings.

    Safe to repeat: if the data store already exists, this function returns without making any changes.

    Parameters
    ----------
    workspace_name : str
        The name of the GeoServer workspace to create the data store in.
    data_store_name : str
        The name to give the created data store.
    steps : list[int | float]
        The graticule line spacings, in degrees, that the data store will generate (e.g. [15] for lines every
        15 degrees).

    Raises
    ----------
    HTTPError
        If geoserver responds with an error, raises it as an exception since it is unexpected.
    """
    data_store_full_name = f"{workspace_name}:{data_store_name}"
    log.info(f"Creating datastore '{data_store_full_name}' if it does not already exist.")

    data_store_url = get_data_store_url(workspace_name, data_store_name)
    if does_resource_exist(data_store_url):
        # If the data store exists then we don't need to do anything
        log.debug(f"Datastore '{data_store_full_name}' already exists.")
        return

    # Manually create the directory to ensure its permissions allow us to write to it later.
    data_store_directory = EnvVariable.DATA_DIR_GEOSERVER / "workspaces" / workspace_name / data_store_name
    data_store_directory.mkdir(parents=True, exist_ok=True)

    # Read the template xml file in a way that works for downstream users of the eddie library.
    graticule_data_store_template = resources.read_text(
        GRATICULE_TEMPLATES_RESOURCE_MODULE,
        "graticule_store_template.xml"
    )
    # set steps to comma-separated string
    steps_values = ", ".join(str(step) for step in steps)
    # Fill template
    graticule_data_store_payload = graticule_data_store_template.format(
        workspace_name=workspace_name,
        data_store_name=data_store_name,
        steps_values=steps_values
    )

    create_ds_response = requests.post(
        f"{get_workspace_url(workspace_name)}/datastores",
        headers=_xml_header,
        data=graticule_data_store_payload,
        auth=(EnvVariable.GEOSERVER_ADMIN_NAME, EnvVariable.GEOSERVER_ADMIN_PASSWORD)
    )
    if create_ds_response.status_code == HTTPStatus.CREATED:
        log.info(f"Created new graticules data store '{data_store_full_name}'.")
    else:
        # If it does not meet the expected results then raise an error
        # Raise error manually so we can configure the text
        raise requests.HTTPError(create_ds_response.text, response=create_ds_response)


if __name__ == '__main__':
    the_ds = "graticules_15_t1"
    the_ws = "static_files"
    the_layer = "graticules_15_t1_layer"
    the_steps = [15]
    from eddie.digitaltwin.utils import LogLevel, setup_logging

    setup_logging(LogLevel.DEBUG)
    create_workspace_if_not_exists(the_ws)
    create_graticules_layer(the_ws, the_ds, the_layer, the_steps)
