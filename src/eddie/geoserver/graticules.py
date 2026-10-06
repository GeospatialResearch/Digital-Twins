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
from eddie.geoserver.geoserver_common import does_resource_exist, get_data_store_url, get_workspace_url

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

    Raises
    ----------
    HTTPError
        If geoserver responds with an error, raises it as an exception since it is unexpected.
    """
    # Ensure the data store this layer will be served from exists before configuring the layer itself.
    create_data_store_for_graticules_layer_if_not_exists(workspace_name, data_store_name, steps)
    log.info(f"Creating graticules layer '{layer_name}'.")
    data_store_url = get_data_store_url(workspace_name, data_store_name)
    layer_url = f"{data_store_url}/featuretypes/{layer_name}"
    if does_resource_exist(layer_url):
        log.debug(f"Layer '{layer_name}' already exists.")
        return

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

    # Create the feature type through GeoServer's REST API, the same way as for any other vector store.
    # GeoServer auto-creates the default layer for a feature type as part of this call, so no separate
    # "create the layer" request is needed for the layer to appear and be servable over WMS/WFS.
    create_featuretype_response = requests.post(
        f"{data_store_url}/featuretypes",
        headers=_xml_header,
        data=featuretype_payload,
        auth=(EnvVariable.GEOSERVER_ADMIN_NAME, EnvVariable.GEOSERVER_ADMIN_PASSWORD)
    )
    if create_featuretype_response.status_code != HTTPStatus.CREATED:
        # Raise error manually so we can configure the text
        raise requests.HTTPError(create_featuretype_response.text, response=create_featuretype_response)
    log.info(f"Created feature type and layer '{layer_name}'.")

    # Construct the layer payload from its template, in the same way as the feature type above. This is a
    # follow-up PUT rather than a creation call, because the featuretype POST above already auto-created the
    # layer: this step only overwrites layer-level settings (e.g. default style) that the template specifies.
    layer_template = resources.read_text(
        GRATICULE_TEMPLATES_RESOURCE_MODULE,
        "graticule_layer_template.xml"
    )
    layer_payload = layer_template.format(
        workspace_name=workspace_name, layer_name=layer_name
    )
    update_layer_response = requests.put(
        f"{get_workspace_url(workspace_name)}/layers/{layer_name}",
        headers=_xml_header,
        data=layer_payload,
        auth=(EnvVariable.GEOSERVER_ADMIN_NAME, EnvVariable.GEOSERVER_ADMIN_PASSWORD)
    )
    if not update_layer_response.ok:
        # Raise error manually so we can configure the text
        raise requests.HTTPError(update_layer_response.text, response=update_layer_response)


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
