import os
import base64
import copy
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import (
    PlainScalarString,
    LiteralScalarString,
    ScalarString,
    FoldedScalarString,
)
from ruamel.yaml.comments import CommentedSeq
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from .sync_gitignore import sync_gitignore
from .places_utils import (
    derive_key,
    convert_string_value,
)


def decrypt_value(
    encrypted_value, keys_dict, original_value, current_var=None, settings=None
):
    """
    Decrypt an encrypted value using the specified keys.
    Returns the decrypted value, or the original value if decryption fails.
    """
    try:
        if not encrypted_value.startswith("encrypted("):
            print(f"Warning: Value for '{current_var}' is not encrypted.")
            return original_value

        key_info, enc_data = encrypted_value[len("encrypted(") :].split("):", 1)
        key_names = key_info.split("|")

        if "|" in enc_data:
            return decrypt_with_compound_key(
                enc_data, keys_dict, key_names, original_value, current_var, settings
            )
        else:
            key_name = key_names[0]
            key_path = keys_dict.get(key_name)
            if not key_path:
                print(
                    f"Warning: Key '{key_name}' not found for variable '{current_var}'."
                )
                return original_value
            return decrypt_single_value(
                enc_data, key_path, original_value, current_var, settings
            )
    except Exception as e:
        print(f"Warning: Invalid encrypted format for '{current_var}': {e}")
        return original_value


def decrypt_single_value(
    encrypted_value, key_path, original_value, current_var=None, settings=None
):
    """
    Decrypt a single encrypted value using the key from the specified key_path.
    """
    try:
        if not os.path.isfile(key_path):
            print(
                f"Warning: Key file '{key_path}' does not exist for variable '{current_var}'."
            )
            return original_value

        with open(key_path, "rb") as key_file:
            password = key_file.read()
        key = derive_key(password, settings)

        encrypted_data = base64.b64decode(encrypted_value)
        aesgcm = AESGCM(key)
        b64_data = aesgcm.decrypt(b"0" * 12, encrypted_data, None)

        decrypted_bytes = base64.b64decode(b64_data)
        decrypted = decrypted_bytes.decode("utf-8")

        if decrypted.startswith("[") and decrypted.endswith("]"):
            items = decrypted.strip("[]").split(",")
            converted_items = [convert_string_value(item.strip()) for item in items]

            seq = CommentedSeq(converted_items)
            seq.fa.set_flow_style()
            return seq

        return copy_scalar_format(convert_string_value(decrypted), original_value)

    except Exception as e:
        print(
            f"Warning: Decryption failed for '{current_var}': {e}. Using original value."
        )
        return original_value


def decrypt_with_compound_key(
    encrypted_values_str,
    keys_dict,
    key_names,
    original_value,
    current_var=None,
    settings=None,
):
    """Decrypt using multiple keys and encrypted values."""
    encrypted_values = encrypted_values_str.split("|")
    if len(key_names) != len(encrypted_values):
        print("Warning: Number of keys and encrypted values do not match.")
        return original_value

    for key_name, enc_value in zip(key_names, encrypted_values):
        decrypted = decrypt_single_value(
            enc_value, keys_dict.get(key_name), None, current_var, settings
        )
        if decrypted:
            return decrypted

    return original_value


def handle_list_value(value, var_name=None, had_comment=False, orig_value=None):
    """Clean up list values after decryption while preserving types and comments."""
    if isinstance(value, str):
        if value.strip().startswith("[") and value.strip().endswith("]"):
            # Parse the string into a list
            items = []
            for item in value[1:-1].split(","):
                item = item.strip().strip("'\"")
                typed_item = convert_value_type(item)
                items.append(typed_item)

            seq = CommentedSeq(items)
            seq.fa.set_flow_style()

            if isinstance(orig_value, CommentedSeq):
                seq.ca = copy.deepcopy(orig_value.ca)

            return seq
    return value


def convert_value_type(value):
    """Convert string value to appropriate type (int, float, bool)."""
    return convert_string_value(value)


def cleanup_inline_comments(filepath):
    """Clean up inline comments to have exactly one space before the comment."""
    with open(filepath, "r") as file:
        lines = file.readlines()

    cleaned_lines = []
    for line in lines:
        if "#" in line:
            parts = line.split("#", 1)
            if len(parts) == 2 and parts[0].strip():

                cleaned_line = f"{parts[0].rstrip()} #{parts[1]}"
                cleaned_lines.append(cleaned_line)
            else:
                cleaned_lines.append(line)
        else:
            cleaned_lines.append(line)

    with open(filepath, "w") as file:
        file.writelines(cleaned_lines)


def preserve_multiline_format(value, orig_value):
    """Preserve multiline block scalar format and indentation."""
    if isinstance(orig_value, str) and (
        orig_value.startswith("|") or orig_value.startswith(">")
    ):

        lines = str(value).split("\n")
        if len(lines) > 1:

            if not str(value).endswith("\n"):
                value = value + "\n"
            return copy_scalar_format(value, orig_value)
    return value


def copy_scalar_format(new_value, original):
    """Copy scalar format (style and indentation) from original to new value."""
    if isinstance(original, ScalarString):
        if original.style in ["|", "|-", "|+"]:
            scalar = LiteralScalarString(new_value)
            scalar.style = original.style
            return scalar
        elif original.style in [">", ">-", ">+"]:
            scalar = FoldedScalarString(new_value)
            scalar.style = original.style
            return scalar
        else:
            return PlainScalarString(new_value)
    return new_value


def format_json_block(value):
    """Convert JSON string with escaped newlines to block format."""
    if isinstance(value, str):
        if value.startswith("{") and "\n" in value.replace("\\n", "\n"):
            formatted = value.replace("\\n", "\n").strip("\"'")
            return LiteralScalarString(formatted)
    return value


def main(source: str, output: str):
    yaml = YAML()
    yaml.preserve_quotes = False
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.width = None

    with open(source, "r") as file:
        data = yaml.load(file)

    data_copy = copy.deepcopy(data)

    all_keys_dict = data.get("keys", {})
    if not all_keys_dict:
        default_key = data.get("key")
        if not default_key:
            print("Error: No default key is set in the configuration.")
            return
        all_keys_dict = {"default": default_key}

    settings = data.get("settings", {"sync-gitignore": True})

    if "variables" in data:
        for var_name, var_data in data["variables"].items():
            orig_value = data_copy["variables"][var_name]

            var_comment = None
            if var_name in data["variables"].ca.items:
                var_comment = data["variables"].ca.items[var_name]

            var_comment = None
            if var_name in data["variables"].ca.items:
                var_comment = data["variables"].ca.items[var_name]

                if var_comment is not None:
                    for pos in (2, 1, 0):
                        if isinstance(var_comment[pos], list) and var_comment[pos]:
                            for comment in var_comment[pos]:
                                if hasattr(comment, "value"):
                                    comment.value = (
                                        " " + comment.value.lstrip().rstrip()
                                    )

            orig_value = data_copy["variables"][var_name]
            if isinstance(var_data, str) and var_data.startswith("encrypted("):

                decrypted_value = decrypt_value(
                    var_data,
                    all_keys_dict,
                    original_value=var_data,
                    current_var=var_name,
                    settings=settings,
                )

                if isinstance(
                    decrypted_value, str
                ) and decrypted_value.strip().startswith("["):
                    formatted_value = handle_list_value(
                        decrypted_value,
                        var_name,
                        had_comment=bool(var_comment),
                        orig_value=orig_value,
                    )

                    data["variables"][var_name] = formatted_value
                    if var_comment:
                        data["variables"].ca.items[var_name] = var_comment
                else:

                    formatted_value = preserve_multiline_format(
                        decrypted_value, orig_value
                    )
                    data["variables"][var_name] = formatted_value

            elif isinstance(var_data, CommentedSeq):

                decrypted_value = [
                    decrypt_value(
                        item,
                        all_keys_dict,
                        original_value=item,
                        current_var=var_name,
                        settings=settings,
                    )
                    for item in var_data
                ]

                seq = CommentedSeq(decrypted_value)
                seq.ca = copy.deepcopy(var_data.ca)
                data["variables"][var_name] = seq

                if var_comment:
                    data["variables"].ca.items[var_name] = var_comment
            elif isinstance(var_data, dict):

                for env_name, env_value in var_data.items():

                    if isinstance(env_value, dict) and "value" in env_value:
                        if isinstance(env_value["value"], str) and env_value[
                            "value"
                        ].startswith("encrypted("):
                            decrypted_value = decrypt_value(
                                env_value["value"],
                                all_keys_dict,
                                original_value=env_value["value"],
                                current_var=var_name,
                                settings=settings,
                            )

                            formatted_value = format_json_block(decrypted_value)
                            data["variables"][var_name][env_name][
                                "value"
                            ] = formatted_value
                    elif isinstance(env_value, str) and env_value.startswith(
                        "encrypted("
                    ):
                        decrypted_value = decrypt_value(
                            env_value,
                            all_keys_dict,
                            original_value=env_value,
                            current_var=var_name,
                            settings=settings,
                        )

                        formatted_value = format_json_block(decrypted_value)
                        data["variables"][var_name][env_name] = formatted_value

    yaml.dump(data, open(output, "w"))

    cleanup_inline_comments(output)

    if settings.get("sync-gitignore", True):
        sync_gitignore()
