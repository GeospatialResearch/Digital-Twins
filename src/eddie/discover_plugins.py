import importlib
import pkgutil
from types import ModuleType


def discover_plugins() -> dict[str, ModuleType]:
    return {
        name: importlib.import_module(name)
        for finder, name, _is_pkg in pkgutil.iter_modules() if name.startswith('eddie_')
    }