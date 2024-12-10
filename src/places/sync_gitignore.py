import os
import yaml

GITIGNORE = ".gitignore"
PLACES_YAML = "places.yaml"

PLACES_ENTRIES = [
    "places.yaml",
    ".places/keys",
]


def get_env_files():
    """Get all environment files defined in places.yaml."""
    if not os.path.exists(PLACES_YAML):
        return []

    with open(PLACES_YAML, "r") as f:
        config = yaml.safe_load(f)

    env_files = []
    if config and "environments" in config:
        for env in config["environments"].values():
            if "filepath" in env:
                env_files.append(env["filepath"])

    return env_files


def sync_gitignore():
    """Sync .gitignore with Places entries."""
    if not os.path.exists(GITIGNORE):
        with open(GITIGNORE, "w") as f:
            f.write("")

    with open(GITIGNORE, "r") as f:
        content = f.read()
        lines = content.splitlines()

    places_section_index = -1
    places_envs_index = -1
    modified = False

    for i, line in enumerate(lines):
        if line.strip() == "# Places":
            places_section_index = i
        elif line.strip() == "# Places - generated environments":
            places_envs_index = i

    if places_section_index == -1:
        lines.extend(["", "# Places"])
        places_section_index = len(lines) - 1
        modified = True

    existing_entries = set(lines)
    for entry in PLACES_ENTRIES:
        if entry not in existing_entries:
            lines.insert(places_section_index + 1, entry)
            modified = True

    env_files = get_env_files()
    if env_files:
        if places_envs_index == -1:
            lines.extend(["", "# Places - generated environments"])
            places_envs_index = len(lines) - 1
            modified = True

        for env_file in env_files:
            if env_file not in existing_entries:
                lines.insert(places_envs_index + 1, env_file)
                modified = True

    if modified:
        with open(GITIGNORE, "w") as f:
            f.write("\n".join(lines) + "\n")
        print("Updated .gitignore")
