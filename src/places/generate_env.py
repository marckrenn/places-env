import sys
import copy
from .places_utils import (
    load_source,
    validate_keys,
    initialize_desired,
    extract_environments,
    process_environments,
    process_variables,
    generate_env_files,
    create_alias_map,
)


def format_env_value(value):
    """Format a value for use in an environment file."""
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("{") and stripped.endswith("}") and "\n" in value:
            lines = value.splitlines()
            while lines and not lines[-1].strip():
                lines.pop()
            formatted_json = "\n".join(lines)
            return f"'{formatted_json}'"
        elif " " in value:
            return f"'{value}'"
    elif isinstance(value, (list, tuple)):
        return str(value).replace('"', "'")
    elif isinstance(value, bool):
        return str(value).replace("False", "false").replace("True", "true")
    return str(value)


def generate_env(environment=None, generate_all=False):
    """
    Generate .env files for specified environments or all environments.

    :param environments: List of environment names to generate .env files for.
    :param generate_all: If True, generate .env files for all environments.
    """
    if generate_all and environment:
        print("Error: Cannot specify environments when using --all.", file=sys.stderr)
        sys.exit(1)

    source = load_source("places.yaml")
    validate_keys(source)
    desired = initialize_desired(source)
    all_environments = extract_environments(source)

    process_environments(source, desired, all_environments)
    process_variables(source, desired, all_environments)

    if generate_all:
        selected_environments = list(all_environments)
    elif environment:
        alias_map = create_alias_map(source.get("environments", {}))
        try:
            selected_environments = []
            for env in environment:
                env_value = format_env_value(env) if " " in env else env
                if env in all_environments:
                    selected_environments.append(env)
                elif env in alias_map:
                    selected_environments.append(alias_map[env])
                else:
                    print(
                        f"Error: Environment or alias '{env_value}' not found",
                        file=sys.stderr,
                    )
                    sys.exit(1)
        except ValueError as e:
            print(f"Error: {str(e)}", file=sys.stderr)
            sys.exit(1)
    else:
        print(
            "Error: No environments specified. Use --all or specify environment names.",
            file=sys.stderr,
        )
        sys.exit(1)

    filtered_desired = copy.deepcopy(desired)
    filtered_desired["environments"] = {
        env: desired["environments"][env] for env in selected_environments
    }

    generate_env_files(filtered_desired)
    print("Generation of .env files completed successfully.")
