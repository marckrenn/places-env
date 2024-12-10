from typing import Any
import yaml
import re
import sys
import os
import hashlib
import json
import subprocess
from ruamel.yaml.scalarstring import PreservedScalarString


def error_exit(message):
    print(f"Error: {message}")
    sys.exit(1)


def warning(message):
    print(f"Warning: {message}")


def ensure_list(value):
    """Ensure that the value is a list."""
    if isinstance(value, str):
        return [value]
    elif isinstance(value, list):
        return value
    else:
        return []


def load_source(filename):
    """Load the source YAML file using PyYAML."""
    try:
        with open(filename, "r") as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        error_exit(f"The file '{filename}' was not found.")
    except yaml.YAMLError as e:
        error_exit(f"Error parsing YAML file '{filename}': {e}")


def validate_keys(source):
    """Validate that 'key' and 'keys' definitions do not conflict."""
    if "key" in source and "keys" in source:
        if "default" not in source["keys"]:
            source["keys"]["default"] = source["key"]
        else:
            warning(
                "Both 'key' and 'keys' are defined. 'keys.default' will be used as the default key."
            )
    elif "keys" not in source and "key" in source:
        source["keys"] = {"default": source["key"]}
    elif "keys" not in source and "key" not in source:
        error_exit("No 'key' or 'keys' defined in the source YAML.")


def initialize_desired(source):
    """Initialize the desired data structure based on the source."""
    keys = source.get("keys", {})
    single_key = source.get("key")
    if single_key:
        keys.setdefault("default", single_key)

    return {
        "version": source.get("version", "1.0"),
        "keys": keys,
        "environments": {},
        "variables": {},
    }


def extract_environments(source):
    """Extract all environment names from the source YAML."""
    envs = list(source.get("environments", {}).keys())
    environments = list(source.get("environments", {}).keys())
    return envs + environments


def create_alias_map(desired_envs):
    """Create a mapping from alias to actual environment names."""
    alias_map = {}
    for env_name, env_info in desired_envs.items():
        aliases = ensure_list(env_info.get("alias", []))
        for alias in aliases:
            alias_map[alias] = env_name
    return alias_map


def resolve_aliases(env_list, alias_map):
    """Resolve aliases in a list of environment names."""
    return [alias_map.get(env_name, env_name) for env_name in env_list]


def resolve_environments(var_name, var_def, all_envs, alias_map):
    """Resolve the list of environments for a variable, considering 'for' and 'except'."""
    if isinstance(var_def, dict) and ("for" in var_def or "except" in var_def):
        if "for" in var_def:
            env_list = ensure_list(var_def["for"])
            env_list = resolve_aliases(env_list, alias_map)
        else:
            excluded_envs = set(
                resolve_aliases(ensure_list(var_def["except"]), alias_map)
            )
            env_list = [env for env in all_envs if env not in excluded_envs]
        resolved_envs = []
        for env_name in env_list:
            if env_name in all_envs:
                resolved_envs.append(env_name)
            else:
                error_exit(
                    f"Environment '{env_name}' specified in variable '{var_name}' is not defined."
                )
        return resolved_envs
    else:
        return all_envs


def matches_environment(key, env, alias_map):
    """Check if a key matches an environment, considering aliases."""
    return key == env or alias_map.get(key) == env


def get_env_key(env_name, source_env, desired):
    """Retrieve the key for the given environment."""
    key_reference = source_env.get("key")
    if key_reference:
        if key_reference not in desired["keys"]:
            error_exit(
                f"Key '{key_reference}' referenced in environment '{env_name}' is not defined in 'keys'."
            )
        return key_reference
    elif "default" in desired["keys"]:
        return "default"
    else:
        error_exit(
            f"No default key defined and no key specified for environment '{env_name}'."
        )


def process_environments(source, desired, all_envs):
    """Process environments from source and populate desired['environments']."""
    for env in all_envs:
        source_env = source["environments"].get(env, {})
        env_key = get_env_key(env, source_env, desired)
        aliases = ensure_list(source_env.get("alias", []))
        desired["environments"][env] = {
            "filepath": source_env.get("filepath", ""),
            "alias": aliases,
            "watch": source_env.get("watch", False),
            "key": env_key,
        }


def get_variables(source):
    """
    Collect variables from 'variables', 'vars', and 'secrets' sections.
    Throws an error if duplicate variables are found across sections.
    Also validates variable names and prints warnings if not uppercase.
    """
    variables = {}
    variable_sources = {}

    for section in ["variables", "vars", "secrets"]:
        section_vars = source.get(section, {})
        for var in section_vars:
            if var in variable_sources:
                existing_sections = variable_sources[var]
                existing_sections.append(section)
                error_exit(
                    f"Duplicate variable key '{var}' found in sections: {', '.join(existing_sections)}."
                )
            else:
                validate_variable_key(var)

                variable_sources[var] = [section]
                variables[var] = section_vars[var]

    return variables


def collect_raw_variables(variables, all_envs, desired, alias_map):
    """Collect raw variable values without substituting placeholders."""
    raw_variables = {}
    for var_name, var_def in variables.items():
        envs_for_var = resolve_environments(var_name, var_def, all_envs, alias_map)
        for env in envs_for_var:
            if isinstance(var_def, dict):
                # Handle global settings
                global_value = var_def.get("value")
                global_key = var_def.get("key")
                global_unencrypted = var_def.get("unencrypted", False)
                if global_value is not None:
                    raw_variables.setdefault(var_name, {}).setdefault(
                        env,
                        {
                            "value": global_value,
                            "key": global_key,
                            "unencrypted": global_unencrypted,
                        },
                    )
                # Handle environment-specific overrides
                for key, env_specific in var_def.items():
                    if key in ["value", "key", "unencrypted", "for", "except"]:
                        continue
                    if matches_environment(key, env, alias_map):
                        env_value, env_key, env_unencrypted = parse_env_specific(
                            env_specific, global_unencrypted
                        )
                        value_to_use = (
                            env_value if env_value is not None else global_value
                        )
                        unencrypted_to_use = env_unencrypted
                        key_to_use = env_key if env_key else global_key
                        if value_to_use is not None:
                            raw_variables.setdefault(var_name, {}).setdefault(
                                env,
                                {
                                    "value": value_to_use,
                                    "key": key_to_use,
                                    "unencrypted": unencrypted_to_use,
                                },
                            )
            else:
                # var_def is a direct value
                var_value = var_def
                if var_value is not None:
                    raw_variables.setdefault(var_name, {}).setdefault(
                        env, {"value": var_value, "key": None, "unencrypted": False}
                    )
    return raw_variables


def parse_env_specific(env_specific, global_unencrypted):
    """Parse environment-specific variable definitions."""
    if isinstance(env_specific, dict):
        env_value = env_specific.get("value")
        env_key = env_specific.get("key")
        env_unencrypted = env_specific.get("unencrypted", global_unencrypted)
    else:
        env_value = env_specific
        env_key = None
        env_unencrypted = global_unencrypted
    return env_value, env_key, env_unencrypted


def substitute_placeholders(value, env, variables, var_name, visited=None):
    """Recursively substitute placeholders in a value string or list."""
    if visited is None:
        visited = set()

    if isinstance(value, list):
        return [
            substitute_placeholders(item, env, variables, var_name, visited)
            for item in value
        ]
    if isinstance(value, str):
        # Match ${VAR} pattern
        placeholders = re.findall(r"\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}", value)
        for placeholder in placeholders:
            if placeholder == var_name or placeholder in visited:
                warning(
                    f"Circular reference detected in variable '{var_name}' for environment '{env}'."
                )
                continue
            if placeholder in variables and env in variables[placeholder]:
                substitution = variables[placeholder][env]["value"]
                visited.add(var_name)
                substitution = substitute_placeholders(
                    substitution, env, variables, placeholder, visited
                )
                visited.remove(var_name)
                value = value.replace(f"${{{placeholder}}}", str(substitution))
            else:
                warning(
                    f"Variable '{placeholder}' used in '{var_name}' is not defined for environment '{env}'."
                )
    return value


def get_variable_key(var_name, var_entry, env, desired):
    """Determine the key for a variable in an environment."""
    unencrypted = var_entry.get("unencrypted", False)
    key_reference = var_entry.get("key")
    if unencrypted:
        return None
    elif key_reference:
        if key_reference not in desired["keys"]:
            error_exit(
                f"Key '{key_reference}' referenced in variable '{var_name}' for environment '{env}' is not defined in 'keys'."
            )
        return key_reference
    else:
        env_key = desired["environments"][env]["key"]
        if env_key in desired["keys"]:
            return env_key
        else:
            error_exit(
                f"Environment key '{env_key}' for environment '{env}' is not defined in 'keys'."
            )


def process_variables(source, desired, all_envs):
    """Process all variables from the source and populate desired['variables']."""
    variables = get_variables(source)
    alias_map = create_alias_map(desired["environments"])
    raw_variables = collect_raw_variables(variables, all_envs, desired, alias_map)

    for var_name, envs in raw_variables.items():
        for env, var_entry in envs.items():
            value = var_entry["value"]
            substituted_value = substitute_placeholders(
                value, env, raw_variables, var_name
            )
            key = get_variable_key(var_name, var_entry, env, desired)
            if var_name not in desired["variables"]:
                desired["variables"][var_name] = {}
            desired["variables"][var_name][env] = {
                "value": substituted_value,
                "unencrypted": var_entry.get("unencrypted", False),
                "key": key,
            }


def is_valid_substitution(value):
    """Check if a variable substitution is properly formatted."""
    stack = []
    in_var = False
    i = 0
    while i < len(value):
        if value[i : i + 2] == "${":
            if in_var:
                return False
            stack.append("${")
            in_var = True
            i += 2
            continue
        elif in_var and value[i] == "}":
            if not stack:
                return False
            stack.pop()
            in_var = False
        i += 1
    return not stack


def is_encrypted_value(value):
    """Check if a value appears to be an encrypted value."""
    return isinstance(value, str) and value.strip().startswith("encrypted(")


def is_json(string):
    try:
        json.loads(string)
    except ValueError:
        return False
    return True


def format_env_value(value, var_name=None, filepath=None):
    """Format the environment variable value with appropriate quotes."""
    if isinstance(value, list):
        # Process each item in the list separately
        formatted_items = []
        for item in value:
            if isinstance(item, (int, float, bool)):
                # Don't quote numbers or booleans
                formatted_items.append(str(item))
            elif isinstance(item, str):
                if any(char in item for char in " \t\n#'\""):
                    # Quote strings with special characters
                    formatted_items.append(f"'{item}'")
                else:
                    # Don't quote simple strings that look like numbers
                    try:
                        float(item)
                        formatted_items.append(item)
                    except ValueError:
                        formatted_items.append(f"'{item}'")
            else:
                formatted_items.append(str(item))
        return f'"[{", ".join(formatted_items)}]"'
    elif is_json(str(value)) and "\n" in str(value):
        if '"' in str(value):
            return f"'{value.rstrip().rstrip()}'"
        elif "'" in str(value):
            return f'"{value.rstrip().rstrip()}"'
        else:
            print("Cant mix")

    # Handle list string representation
    if (
        isinstance(value, str)
        and value.strip().startswith("[")
        and value.strip().endswith("]")
    ):
        try:
            # Parse and reformat list
            inner_value = value.strip()[1:-1]
            items = [item.strip() for item in inner_value.split(",")]
            formatted_items = []
            for item in items:
                if "{{" in item and "}}" in item:
                    formatted_items.append(f"'{item}'")
                elif any(char in item for char in " \t\n#'\""):
                    formatted_items.append(f"'{item}'")
                else:
                    try:
                        float(item)
                        formatted_items.append(item)
                    except ValueError:
                        formatted_items.append(f"'{item}'")
            return f"[{', '.join(formatted_items)}]"
        except:
            pass

    if not isinstance(value, str):
        value = str(value)

    if is_encrypted_value(value):
        # Truncate the value to first 20 characters and add "..." if longer
        truncated_value = value[:20] + ("..." if len(value) > 20 else "")
        if var_name and filepath:
            warning(
                f"Writing unencrypted value '{truncated_value}' for variable '{var_name}' while processing '{filepath}'"
            )
        else:
            warning(f"Writing unencrypted value '{truncated_value}'")

    # Detect improper substitutions
    if not is_valid_substitution(value):
        warning(f"Substitution is not properly formatted in value: {value}")

    # Avoid wrapping ${...} in quotes
    if re.match(r"^\$\{[^}]+\}$", value) or re.match(
        r"^\$[A-Za-z_][A-Za-z0-9_]*$", value
    ):
        return value

    special_chars = set(" \t\n#'\"")
    needs_quotes = (
        any(char in special_chars for char in value)
        or value.startswith("#")
        or "\n" in value
    )

    if not needs_quotes:
        return value

    if "'" not in value:
        return f"'{value.rstrip()}'"
    elif '"' not in value:
        return f'"{value.rstrip()}"'
    else:
        # For multiline strings, it's better to use double quotes and escape any double quotes inside
        escaped_value = value.replace('"', '\\"')
        return f'"{escaped_value}"'


def get_git_project_name():
    """Get the git project name from remote URL or directory name."""
    try:
        # Try to get the remote URL
        remote_url = (
            subprocess.check_output(
                ["git", "config", "--get", "remote.origin.url"],
                stderr=subprocess.DEVNULL,
            )
            .decode("utf-8")
            .strip()
        )
        # Extract project name from remote URL
        project_name = remote_url.split("/")[-1].replace(".git", "")
        return project_name
    except subprocess.CalledProcessError:
        # Fallback to directory name if git command fails
        try:
            git_root = (
                subprocess.check_output(
                    ["git", "rev-parse", "--show-toplevel"], stderr=subprocess.DEVNULL
                )
                .decode("utf-8")
                .strip()
            )
            return os.path.basename(git_root)
        except subprocess.CalledProcessError:
            error_exit("Not a git repository")


def get_git_branch():
    """Get the current git branch name."""
    try:
        branch = (
            subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.DEVNULL
            )
            .decode("utf-8")
            .strip()
        )
        return branch
    except subprocess.CalledProcessError:
        error_exit("Not a git repository")


def get_salt(salt_settings):
    """Get salt based on the provided settings."""
    salt_mode = salt_settings.get("mode", "deterministic")
    deterministic_salt = "deterministic_salt"
    salt = ""

    if salt_mode == "deterministic":
        salt = deterministic_salt
    elif salt_mode == "custom":
        salt = salt_settings.get("value", deterministic_salt)
    elif salt_mode == "from-file":
        path = salt_settings.get("filepath")
        if not path or not os.path.exists(path):
            error_exit(f"Salt file '{path}' does not exist.")
        with open(path, "r") as file:
            salt = file.read().strip()
    elif salt_mode == "git-project":
        salt = get_git_project_name()
    elif salt_mode == "git-branch":
        salt = get_git_branch()
    elif salt_mode == "git-project-branch":
        project_name = get_git_project_name()
        branch_name = get_git_branch()
        salt = f"{project_name}-{branch_name}"
    else:
        salt = deterministic_salt

    return bytes(str(salt), encoding="utf_8")


# OWASP recommended iterations for different hash algorithms
OWASP_ITERATIONS = {"sha256": 600000, "sha512": 210000}

DEFAULT_CRYPTO_SETTINGS = {
    "hash-function": "sha512",
    "dklen": 32,
    "salt": {"mode": "deterministic"},
}


def derive_key(password, settings):
    """
    Derive a 32-byte key using PBKDF2 with configurable hash algorithm and salt.
    Uses OWASP recommended iterations for common hash algorithms.
    """
    cryptography = settings.get("cryptography", {})

    # Get hash algorithm with default
    hash_function = cryptography.get(
        "hash-function", DEFAULT_CRYPTO_SETTINGS["hash-function"]
    )

    # Set iterations based on hash algorithm
    default_iterations = OWASP_ITERATIONS.get(hash_function, OWASP_ITERATIONS["sha512"])
    iterations = cryptography.get("iterations", default_iterations)

    # Get remaining parameters with defaults
    dklen = cryptography.get("dklen", DEFAULT_CRYPTO_SETTINGS["dklen"])
    salt_settings = cryptography.get("salt", DEFAULT_CRYPTO_SETTINGS["salt"])

    salt = get_salt(salt_settings)
    return hashlib.pbkdf2_hmac(hash_function, password, salt, iterations, dklen)


def is_encrypted(value):
    """Check if a value is already encrypted."""
    return isinstance(value, str) and value.strip().startswith("encrypted(")


def process_value_with_comment(line_value):
    """Extract value and comment, handling quotes and whitespace correctly."""
    parts = line_value.split("#", 1)
    value = parts[0].strip()
    comment = ""
    if len(parts) > 1:
        spaces_before_comment = len(parts[0]) - len(parts[0].rstrip())
        comment = " " * spaces_before_comment + "#" + parts[1]
    return value, comment


def validate_key_name(key_name):
    """Validate that the key name doesn't contain invalid characters."""
    if "|" in key_name:
        error_exit("Key name cannot contain the '|' character")


def format_json_value(value, base_indent=0):
    """Format multiline strings and JSON values appropriately"""
    if isinstance(value, str):
        if "\n" in value or (value.strip().startswith("{") and "#" in value):
            return PreservedScalarString(value)
    return value


def clean_template_vars(value):
    """Remove unnecessary quotes and wrap template variable values in quotes"""
    if isinstance(value, (int, float, bool)):
        return value

    if isinstance(value, list):
        return [clean_template_vars(item) for item in value]

    if isinstance(value, str):
        # Try converting to number first
        try:
            if value.isdigit():
                return int(value)
            float_val = float(value)
            return int(float_val) if float_val.is_integer() else float_val
        except ValueError:
            pass

    return value


def validate_variable_key(var):
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", var):
        error_exit(
            f"Variable name '{var}' is invalid. It must start with a letter or underscore, followed by only letters, digits, or underscores."
        )

    if var != var.upper():
        warning(f"Variable name '{var}' is not uppercase.")


def clean_value(value):
    """Remove unnecessary quotes and convert to appropriate type."""
    if isinstance(value, list):
        return [clean_value(item) for item in value]
    if isinstance(value, str):
        # Handle array notation in strings
        if value.strip().startswith("[") and value.strip().endswith("]"):
            try:
                # Convert string representation of list to actual list
                inner_value = value.strip()[1:-1]
                items = [item.strip() for item in inner_value.split(",")]
                return [clean_value(item) for item in items]
            except:
                pass
        value = value.strip('"').strip("'")
        # Try converting to number
        if value.isdigit():
            return int(value)
        try:
            float_val = float(value)
            # Check if it's a whole number
            if float_val.is_integer():
                return int(float_val)
            return float_val
        except ValueError:
            pass
        # Try converting to boolean
        if value.lower() == "true":
            return True
        elif value.lower() == "false":
            return False
        return value
    return value


def generate_env_files(desired, selected_envs=None):
    """Generate .env files based on the desired data structure.
    If selected_envs is provided, generate only those environments.
    """
    # Determine which environments to generate
    envs_to_generate = (
        selected_envs if selected_envs else desired["environments"].keys()
    )

    for env_name in envs_to_generate:
        env_info = desired["environments"].get(env_name)
        if not env_info:
            error_exit(
                f"Environment '{env_name}' is not defined in desired['environments']."
            )

        filepath = env_info["filepath"]
        variables = desired["variables"]
        lines = []

        for var_name, var_envs in variables.items():
            if env_name not in var_envs:
                continue

            var_entry = var_envs[env_name]
            value = var_entry["value"]

            formatted_value = format_env_value(
                value, var_name=var_name, filepath=filepath
            )

            # Detect improper substitution in key assignment
            if not is_valid_substitution(formatted_value):
                warning(
                    f"Substitution is not properly performed on key assignment for variable '{var_name}' in environment '{env_name}'."
                )

            lines.append(f"{var_name}={formatted_value}")

        dir_name = os.path.dirname(filepath)
        if dir_name and not os.path.exists(dir_name):
            try:
                os.makedirs(dir_name)
                print(f"Created directory '{dir_name}' for environment '{env_name}'.")
            except OSError as e:
                error_exit(f"Error creating directory '{dir_name}': {e}")

        try:
            with open(filepath, "w") as f:
                f.write("\n".join(lines) + "\n" if lines else "\n")
            print(f"Generated '{filepath}' for environment '{env_name}'.")
        except IOError as e:
            error_exit(f"Error writing to .env file '{filepath}': {e}")


def convert_string_value(value: str) -> Any:
    """Convert string value to appropriate Python type"""
    if not isinstance(value, str):
        return value

    # Try to convert to bool
    if value.lower() in ("true", "false"):
        return value.lower() == "true"

    # Try to convert to int/float
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        pass

    return value
