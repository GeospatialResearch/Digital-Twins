import os
from typing import TypeVar

from dotenv import load_dotenv

# Generic type, used for static type checking
T = TypeVar("T")

load_dotenv()


def get_env_variable(var_name: str, default: T = None, allow_empty: bool = False, cast_to: T = str) -> T:
    """
    Reads an environment variable, with settings to allow defaults, empty values, and type casting

    :param var_name: The name of the environment variable to retrieve.
    :param default: Default return value if the environment variable does not exist. Does not override empty env variables.
    :param allow_empty: If False then a KeyError will be raised if the environment variable is empty.
    :param cast_to: the type that the variable is cast to when returned e.g. int or bool.
    :return: The environment variable, or default if it does not exist.
    :raises KeyError if allow_empty is False and the environment variable is empty string or None
    :raises ValueError if cast_to is not compatible with the value stored.
    """
    env_var = os.getenv(var_name, default)
    if not allow_empty and env_var in (None, ""):
        raise KeyError(f"Environment variable {var_name} not set, and allow_empty is False")
    return _cast_str(env_var, cast_to)


def _cast_str(str_to_cast: str, cast_to: T) -> T:
    """
    Takes a string and casts it to necessary primitive builtin types. Tested with int, float, and bool.
    For bools this detects if the value is in the case-insensitive sets {"True", "T", "1"} or {"False", "F", "0"}
    and raises a ValueError if not

    :param str_to_cast: the string that is going to be casted to the type
    :param cast_to: the type to cast to e.g. bool
    :return: The string casted to cast_to type
    :raises ValueError if cast_to is not compatible with the value stored
    """
    # Special cases i.e. casts that aren't of the form int("7") -> 7
    # For bool we have the problem where bool("False") == True because it detects that len("False") > 0 so we change it
    if cast_to == bool:
        truth_values = {"true", "t", "1"}
        false_values = {"false", "f", "0"}
        if str_to_cast.lower() in truth_values:
            return True
        elif str_to_cast.lower() in false_values:
            return False
        raise ValueError(f"{str_to_cast} being casted to bool but is not in {truth_values} or {false_values}")
    # General case
    return cast_to(str_to_cast)
