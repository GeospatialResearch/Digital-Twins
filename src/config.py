import os
from typing import Type, TypeVar, Optional

from dotenv import load_dotenv

# Generic type, used for static type checking
T = TypeVar("T", str, bool, int, float)

load_dotenv()
load_dotenv("api_keys.env")


def get_env_variable(var_name: str, default: str = None, allow_empty: bool = False) -> str:
    """
    Reads a string environment variable, with settings to allow defaults, empty values.
    To read a boolean user get_bool_env_variable

    Parameters
    ----------
    var_name : str
        The name of the environment variable to retrieve.
    default : T = None
        Default return value if the environment variable does not exist.
    allow_empty : bool
        If False then a ValueError will be raised if the environment variable is empty.

    Returns
    -------
    The environment variable, or default if it does not exist, as type T.

    Raises
    ------
    KeyError
        If allow_empty is False and the environment variable is empty string or None
    """
    env_var = os.getenv(var_name)
    if default is not None and env_var in (None, ""):
        # Set env_var to default, but do not override empty str with None
        env_var = default
    if not allow_empty and env_var in (None, ""):
        raise KeyError(f"Environment variable {var_name} not set, and allow_empty is False")
    return env_var


def get_bool_env_variable(var_name: str, default: Optional[bool] = None, allow_empty: bool = False) -> bool:
    """
    Reads an environment variable and attempts to cast to bool, with settings to allow defaults, empty values.
    For bool we have the problem where bool("False") == True but we want this function to return False

    Parameters
    ----------
    var_name : str
        The name of the environment variable to retrieve.
    default : Optional[bool] = None
        Default return value if the environment variable does not exist.
    allow_empty : bool
        If False then a KeyError will be raised if the environment variable is empty.

    Returns
    -------
    bool
        The environment variable, or default if it does not exist

    Raises
    ------
    ValueError
        If allow_empty is False and the environment variable is empty string or None
    """
    env_variable = get_env_variable(var_name, default, allow_empty)
    truth_values = {"true", "t", "1"}
    false_values = {"false", "f", "0"}
    if env_variable.lower() in truth_values:
        return True
    elif env_variable.lower() in false_values:
        return False
    raise ValueError(f"Environment variable {var_name}={env_variable} being casted to bool "
                     f"but is not in {truth_values} or {false_values}")
