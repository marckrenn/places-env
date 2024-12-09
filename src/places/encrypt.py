import os
import base64
import sys
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import (
    PlainScalarString,
    LiteralScalarString,
    FoldedScalarString,
)
from ruamel.yaml.comments import CommentedSeq
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from .sync_gitignore import sync_gitignore

from .places_utils import (
    derive_key,
    is_encrypted,
    validate_key_name,
    convert_string_value,
)


def encrypt_value(value, key_path, current_var=None, settings=None):
    """
    Encrypt a value using the key from the specified key_path.
    Returns the encrypted value as a base64-encoded string, or exits if key file is missing.
    """
    try:
        value = convert_string_value(value)

        if isinstance(value, (int, float, bool)):
            value = str(value)
        elif isinstance(value, (list, CommentedSeq)):
            items = [str(item) for item in value]
            value = f"[{','.join(items)}]"

        if isinstance(value, str):
            if not (value.startswith("[") and value.endswith("]")):
                value = value.strip("'\"")

        input_bytes = str(value).encode("utf-8")
        b64_data = base64.b64encode(input_bytes).replace(b"\n", b"").replace(b"\r", b"")

        if not os.path.isfile(key_path):
            print(
                f"Error: Key file '{key_path}' does not exist for variable '{current_var}'."
            )
            sys.exit(1)

        with open(key_path, "rb") as key_file:
            password = key_file.read()
        key = derive_key(password, settings)

        aesgcm = AESGCM(key)
        encrypted_data = aesgcm.encrypt(b"0" * 12, b64_data, None)

        return base64.b64encode(encrypted_data).decode("utf-8")
    except Exception as e:
        print(f"Warning: Encryption failed for variable '{current_var}': {e}")
        return None


def resolve_env(env_name, environments):
    """
    Resolve the actual environment configuration from the environment name or alias.
    """
    alias_map = {}
    for actual_env, config in environments.items():
        aliases = config.get("alias", [])
        for alias in aliases:
            alias_map[alias] = actual_env

    resolved_env = alias_map.get(env_name, env_name)
    return environments.get(resolved_env)


def get_env_keys(environments):
    """Get a sorted list of unique keys used across environments."""
    keys = set()
    for env_config in environments.values():
        key = env_config.get("key", "default")
        keys.add(key)
    return sorted(list(keys))


def encrypt_with_compound_key(
    value, keys_dict, key_names, current_var=None, settings=None
):
    """Encrypt a value using multiple keys separately with sorted keys."""
    try:
        value = convert_string_value(value)

        if isinstance(value, (int, float, bool)):
            value = str(value)
        elif isinstance(value, list):
            value = str(value)

        if (
            isinstance(value, str)
            and value.strip().startswith("[")
            and value.strip().endswith("]")
        ):
            value = f"'{value}'"

        if isinstance(value, str):
            value = value.strip("'\"")

        sorted_key_names = sorted(key_names)
        encrypted_values = []
        used_key_names = []

        for key_name in sorted_key_names:
            key_path = keys_dict.get(key_name)
            if not key_path:
                print(
                    f"Warning: Key '{key_name}' not found for variable '{current_var}'."
                )
                continue

            if not os.path.isfile(key_path):
                print(
                    f"Warning: Key file '{key_path}' does not exist for variable '{current_var}'."
                )
                continue

            if isinstance(value, list):
                value_str = str(value)[1:-1]
            else:
                value_str = str(value)

            try:
                input_bytes = value_str.encode("utf-8")
                b64_data = (
                    base64.b64encode(input_bytes)
                    .replace(b"\n", b"")
                    .replace(b"\r", b"")
                )

                with open(key_path, "rb") as key_file:
                    password = key_file.read()
                key = derive_key(password, settings)

                aesgcm = AESGCM(key)
                encrypted_data = aesgcm.encrypt(b"0" * 12, b64_data, None)
                encrypted_value = base64.b64encode(encrypted_data).decode("utf-8")

                encrypted_values.append(encrypted_value)
                used_key_names.append(key_name)
            except Exception as e:
                print(
                    f"Warning: Encryption failed with key '{key_name}' for variable '{current_var}': {e}"
                )
                continue

        if not encrypted_values:
            return None

        compound_key_name = "|".join(used_key_names)
        return f"encrypted({compound_key_name}):{('|'.join(encrypted_values))}"

    except Exception as e:
        print(f"Warning: Encryption failed for variable '{current_var}': {e}")
        return None


def format_list_value(value):
    """Format a list value by adding appropriate quotes."""
    if isinstance(value, (list, CommentedSeq)):
        items = [str(item) for item in value]
        return f"[{', '.join(items)}]"
    return value


def main(source: str, output: str):
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = False
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.width = 4096

    with open(source, "r") as file:
        data = yaml.load(file)

    all_keys_dict = data.get("keys", {})
    if not all_keys_dict:
        default_key = data.get("key")
        if not default_key:
            print("Error: No default key is set in the configuration.")
            return
        validate_key_name("default")
        all_keys_dict = {"default": default_key}

    environments = data.get("environments", {})
    settings = data.get("settings", {"sync-gitignore": True})

    env_key_map = {}
    for env_name, env_config in environments.items():
        env_key_map[env_name] = env_config.get("key", "default")
        for alias in env_config.get("alias", []):
            env_key_map[alias] = env_config.get("key", "default")

    if not env_key_map:
        env_key_map["default"] = "default"

    if "variables" in data:
        for var_name, var_data in data["variables"].items():
            if isinstance(var_data, (str, int, float, bool)):

                value = (
                    format_list_value(var_data)
                    if isinstance(var_data, list)
                    else str(var_data)
                )
                if not is_encrypted(value):
                    sorted_keys = sorted(set(env_key_map.values()))
                    encrypted_value = encrypt_with_compound_key(
                        value, all_keys_dict, sorted_keys, var_name, settings
                    )
                    if encrypted_value:
                        if isinstance(var_data, LiteralScalarString):
                            encrypted_node = LiteralScalarString(encrypted_value)
                        elif isinstance(var_data, FoldedScalarString):
                            encrypted_node = FoldedScalarString(encrypted_value)
                        else:
                            encrypted_node = PlainScalarString(encrypted_value)
                        data["variables"][var_name] = encrypted_node
            elif isinstance(var_data, (list, CommentedSeq)):
                if not is_encrypted(str(var_data)):
                    value = format_list_value(var_data)
                    sorted_keys = sorted(set(env_key_map.values()))
                    encrypted_value = encrypt_with_compound_key(
                        value, all_keys_dict, sorted_keys, var_name, settings
                    )
                    if encrypted_value:
                        data["variables"][var_name] = PlainScalarString(encrypted_value)
            elif isinstance(var_data, dict):
                if "value" in var_data and not var_data.get("unencrypted", False):
                    value = var_data["value"]
                    if not is_encrypted(str(value)):
                        key_field = var_data.get("key", "default")
                        encrypted_value = encrypt_value(
                            value, all_keys_dict.get(key_field), var_name, settings
                        )
                        if encrypted_value:
                            enc_str = f"encrypted({key_field}):{encrypted_value}"
                            data["variables"][var_name]["value"] = PlainScalarString(
                                enc_str
                            )

                for env_name, env_value in var_data.items():
                    if env_name in environments or env_name in env_key_map:
                        if isinstance(env_value, (str, int, float, bool, list)):
                            if not is_encrypted(str(env_value)):
                                resolved_env = resolve_env(env_name, environments)
                                key_to_use = (
                                    resolved_env.get("key", "default")
                                    if resolved_env
                                    else "default"
                                )
                                encrypted_value = encrypt_value(
                                    env_value,
                                    all_keys_dict.get(key_to_use),
                                    var_name,
                                    settings,
                                )
                                if encrypted_value:
                                    enc_str = (
                                        f"encrypted({key_to_use}):{encrypted_value}"
                                    )
                                    data["variables"][var_name][env_name] = (
                                        PlainScalarString(enc_str)
                                    )

                        elif (
                            isinstance(env_value, dict)
                            and "value" in env_value
                            and not env_value.get("unencrypted", False)
                        ):
                            value = env_value["value"]
                            if not is_encrypted(str(value)):
                                key_field = env_value.get("key", "default")
                                encrypted_value = encrypt_value(
                                    value,
                                    all_keys_dict.get(key_field),
                                    var_name,
                                    settings,
                                )
                                if encrypted_value:
                                    enc_str = (
                                        f"encrypted({key_field}):{encrypted_value}"
                                    )
                                    data["variables"][var_name][env_name]["value"] = (
                                        PlainScalarString(enc_str)
                                    )

    with open(output, "w") as file:
        yaml.dump(data, file)

    if settings.get("sync-gitignore", True):
        sync_gitignore()
