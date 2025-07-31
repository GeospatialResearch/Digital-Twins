import importlib
import logging
import pkgutil
from types import ModuleType

from eddie.digitaltwin.utils import setup_logging

setup_logging()
log = logging.getLogger(__name__)

def discover_plugins() -> dict[str, ModuleType]:
    plugins = {
        name: importlib.import_module(name)
        for _finder, name, _is_pkg in pkgutil.iter_modules() if name.startswith('eddie_')
    }
    log.info(f"Plugins discovered: {plugins}")
    return plugins