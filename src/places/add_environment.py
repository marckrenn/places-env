from typing import List, Optional, Union
from .places_yaml import PlacesYAML
from .places_utils import error_exit

DEFAULT_YAML_PATH = "places.yaml"


def check_existing_environment(env_name: str, yaml_path: str) -> bool:
    """Check if environment exists and ask for confirmation to update"""
    yaml = PlacesYAML(yaml_path)
    if "environments" in yaml.data and env_name in yaml.data["environments"]:
        response = input(
            f"Environment '{env_name}' already exists. Do you want to update it? (y/N): "
        )
        if response.lower() != "y":
            return False
    return True


def add_environment_to_places(
    env_name: str,
    filepath: Optional[str] = None,
    watch: Optional[bool] = None,
    alias: Optional[Union[str, List[str]]] = None,
    key: Optional[str] = None,
    yaml_path: str = DEFAULT_YAML_PATH,
) -> None:
    """Add environment reference to places.yaml"""
    if not env_name:
        error_exit("Environment name cannot be empty")

    exists = check_existing_environment(env_name, yaml_path)
    if not exists:
        error_exit("Environment addition cancelled by user")

    yaml = PlacesYAML(yaml_path)
    yaml.update_environment(
        env_name, filepath=filepath, watch=watch, alias=alias, key=key
    )
    yaml.save()
