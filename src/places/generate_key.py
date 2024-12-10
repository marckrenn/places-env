import os
import secrets
import base64
from collections import Counter
from math import log2
from .places_utils import error_exit, validate_key_name


def calculate_entropy(data):
    """Calculate Shannon entropy (bits per character) of given data."""
    freq = Counter(data)
    total = len(data)
    return -sum((count / total) * log2(count / total) for count in freq.values())


def add_key_to_places(key_name):
    """Add key reference to places.yaml"""
    from .add_key import add_key_to_places as add_key

    add_key(key_name)


def generate_key(
    key_name, length=32, key=None, add_to_places=False, force_overwrite=False
):
    """
    Generate or store a key compatible with AES-GCM and save it under .places/keys/<key_name>

    Args:
        key_name: Name of the key file
        length: Length of the key in bytes (default: 32, only used when generating)
        key: Optional string to use as key (if provided, length is ignored)
        add_to_yaml: If True, add key reference to places.yaml
        force_overwrite: If True, bypass safety checks and overwrite warnings
    """
    validate_key_name(key_name)
    key_to_save = ""

    if key:
        try:
            key_bytes = key.encode("utf-8")
            if len(key_bytes) < 16 and not force_overwrite:
                error_exit("Provided key is too short. Minimum length is 16 bytes.")
            entropy = calculate_entropy(key_bytes)
            if entropy < 3.0 and not force_overwrite:
                response = input(
                    f"Warning: Key has low entropy ({entropy:.2f} bits/char). Do you really want to use this key? (y/N): "
                )
                if response.lower() != "y":
                    error_exit("Key generation cancelled by user")
            key_to_save = key
        except Exception as e:
            error_exit(f"Invalid key format: {e}")
    else:
        if length < 16:
            error_exit("Key length must be at least 16 bytes for security reasons")
        key = secrets.token_bytes(length)
        entropy = calculate_entropy(key)
        if entropy < 3.0:
            response = input(
                f"Warning: Generated key has unexpectedly low entropy ({entropy:.2f} bits/char). Continue anyway? (y/N): "
            )
            if response.lower() != "y":
                error_exit("Key generation cancelled by user")
        key_to_save = base64.b64encode(key).decode("utf-8")

    key_dir = os.path.join(".places", "keys")
    try:
        os.makedirs(key_dir, exist_ok=True)
    except Exception as e:
        error_exit(f"Failed to create directory '{key_dir}': {e}")

    filename = os.path.join(key_dir, key_name)

    if os.path.exists(filename) and not force_overwrite:
        response = input(
            f"Key '{key_name}' already exists. Do you want to overwrite it? (y/N): "
        )
        if response.lower() != "y":
            error_exit("Key generation cancelled by user")

    try:
        with open(filename, "w") as file:
            file.write(key_to_save)
        if os.name == "posix":
            os.chmod(filename, 0o600)
        print(f"Key generated and saved to '{filename}'")

        if add_to_places:
            add_key_to_places(key_name)

    except IOError as e:
        error_exit(f"Error writing key to '{filename}': {e}")
    except Exception as e:
        error_exit(f"Error setting permissions for '{filename}': {e}")
