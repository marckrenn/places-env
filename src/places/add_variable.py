from .places_yaml import PlacesYAML
from .places_utils import (
    validate_variable_key,
    clean_template_vars,
    format_json_value,
    convert_string_value,
)


def add_variable_to_places(
    var_name, value=None, key=None, unencrypt=False, environment=None
):
    """Add variable to places.yaml"""
    validate_variable_key(var_name)

    if value is not None:
        value = clean_template_vars(value)
        value = convert_string_value(value)
        value = format_json_value(value, base_indent=2)

    yaml = PlacesYAML()
    yaml.update_variable(
        var_name, value=value, key=key, unencrypt=unencrypt, environment=environment
    )
    yaml.save()
