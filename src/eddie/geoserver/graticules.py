from http import HTTPStatus
from importlib import resources
import logging
import requests

from eddie.config import EnvVariable
from eddie.geoserver.geoserver_common import (
    create_workspace_if_not_exists, doesResourceExist, forceConfigRefresh, get_data_store_url, get_geoserver_url,
    get_workspace_url
)

log = logging.getLogger(__name__)
_xml_header = {"Content-type": "text/xml"}

DEFAULT_GRATICULE_NAME = "Graticule_15"
DEFAULT_GRATICULE_STEPS = ["15"]

def create_graticules_layer(
    workspace_name: str,
    data_store_name: str = DEFAULT_GRATICULE_NAME,
    layer_name: str = DEFAULT_GRATICULE_NAME,
    steps: list[int | float] = DEFAULT_GRATICULE_STEPS
):
    create_data_store_for_graticules_layer_if_not_exists(workspace_name, data_store_name, steps)
    log.info(f"Creating graticules layer '{layer_name}'.")
    layer_url = f"{get_data_store_url(workspace_name, data_store_name)}/featuretypes/{layer_name}"
    if doesResourceExist(layer_url):
        log.debug(f"Layer '{layer_name}' already exists.")
        return

    layer_directory = EnvVariable.DATA_DIR_GEOSERVER / "workspaces" / workspace_name / data_store_name / layer_name
    layer_directory.mkdir(parents=True, exist_ok=True)

    # Construct payload from template
    featuretype_template = resources.read_text(
        "eddie.geoserver.templates.graticule",
        "graticule_featuretype_template.xml"
    )
    if len(steps) > 1:
        steps_range = f"{min(steps)}_{max(steps)}"
    elif len(steps) == 1:
        steps_range = str(steps[0])
    else:
        steps_range = ""
    featuretype_payload = featuretype_template.format(
        workspace_name=workspace_name, data_store_name=data_store_name, layer_name=layer_name, steps_range=steps_range
    )
    with open(layer_directory / "featuretype.xml", "w") as f:
        f.write(featuretype_payload)

    layer_template = resources.read_text(
        "eddie.geoserver.templates.graticule",
        "graticule_layer_template.xml"
    )
    layer_payload = layer_template.format(
        workspace_name=workspace_name, layer_name=layer_name
    )
    with open(layer_directory / "layer.xml", "w") as f:
        f.write(layer_payload)
    forceConfigRefresh()


def create_data_store_for_graticules_layer_if_not_exists(
    workspace_name: str,
    data_store_name: str,
    steps: list[int | float]
):
    data_store_full_name = f"{workspace_name}:{data_store_name}"
    log.info(f"Creating datastore '{data_store_full_name}' if it does not already exist.")

    data_store_url = get_data_store_url(workspace_name, data_store_name)
    if doesResourceExist(data_store_url):
        # If the data store exists then we don't need to do anything
        log.debug(f"Datastore '{data_store_full_name}' already exists.")
        return

    # Manually create the directory to ensure its permissions allow us to write to it later.
    data_store_directory = EnvVariable.DATA_DIR_GEOSERVER / "workspaces" / workspace_name / data_store_name
    data_store_directory.mkdir(parents=True, exist_ok=True)

    # Read the template xml file in a way that works for downstream users of the eddie library.
    graticule_data_store_template = resources.read_text("eddie.geoserver.templates.graticule",
                                                        "graticule_store_template.xml")
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
    steps = [15]
    from eddie.digitaltwin.utils import LogLevel, setup_logging

    setup_logging(LogLevel.DEBUG)
    create_workspace_if_not_exists(the_ws)
    create_graticules_layer(the_ws, the_ds, the_layer, steps)
