import os
import shutil
import click
from .generate_key import generate_key

PLACES_DIR = ".places"
PLACES_YAML = "places.yaml"
KEYS_DIR = os.path.join(PLACES_DIR, "keys")
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")


class TemplateManager:
    def __init__(self):
        self.template_dir = TEMPLATES_DIR

    def list_templates(self):
        """List all available templates."""
        templates = []
        for item in os.listdir(self.template_dir):
            if item.endswith("_test.yaml"):
                continue
            if item.endswith(".yaml"):
                templates.append(item[:-5])  # Remove .yaml extension
        return templates

    def get_template_path(self, template_name):
        """Get the full path to a template."""
        return os.path.join(self.template_dir, f"{template_name}.yaml")


def initialize_places(template_name=None, list_templates=False):
    """Initialize a new Places configuration using templates."""
    template_mgr = TemplateManager()

    if list_templates:
        templates = template_mgr.list_templates()
        print("Available templates:")
        for template in templates:
            print(f"  - {template}")
        return

    os.makedirs(".places", exist_ok=True)

    if template_name:
        template_path = template_mgr.get_template_path(template_name)
        if not os.path.exists(template_path):
            raise click.ClickException(f"Template '{template_name}' not found")
        shutil.copy2(template_path, "places.yaml")
        print(f"Initialized Places using '{template_name}' template")
        if template_name != "_e2e_test":  # Skip key generation for e2e_test, ooff
            generate_key("default")
    else:
        open("places.yaml", "w").close()
        print("Initialized Places with empty configuration")
