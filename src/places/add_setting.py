from .places_yaml import PlacesYAML
from .places_utils import clean_value


def add_setting_to_places(
    sync_gitignore=None,
    iterations=None,
    hash_function=None,
    salt_mode=None,
    salt_filepath=None,
    salt_value=None,
):
    """Add settings to places.yaml"""
    yaml = PlacesYAML()

    if iterations:
        iterations = clean_value(iterations)
    if hash_function:
        hash_function = clean_value(hash_function)
    if salt_mode:
        salt_mode = clean_value(salt_mode)
    if salt_filepath:
        salt_filepath = clean_value(salt_filepath)
    if salt_value:
        salt_value = clean_value(salt_value)

    yaml.update_settings(
        sync_gitignore=sync_gitignore,
        iterations=iterations,
        hash_function=hash_function,
        salt_mode=salt_mode,
        salt_filepath=salt_filepath,
        salt_value=salt_value,
    )
    yaml.save()
