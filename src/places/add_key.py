from .places_yaml import PlacesYAML
from .places_utils import validate_key_name


def add_key_to_places(key_name: str) -> None:
    """Add key reference to places.yaml"""
    validate_key_name(key_name)
    yaml = PlacesYAML()
    yaml.update_key(key_name, f".places/keys/{key_name}")
    yaml.save()
