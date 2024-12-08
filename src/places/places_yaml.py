from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from typing import Any, Optional
from pathlib import Path


class PlacesYAML:
    def __init__(self, file_path: str = "places.yaml"):
        self.file_path = Path(file_path)
        self.yaml = YAML()
        self.yaml.preserve_quotes = True
        self.yaml.indent(mapping=2, sequence=4, offset=2)
        self.data = self._load()

    def _load(self) -> CommentedMap:
        """Load YAML file or return empty structure if file doesn't exist"""
        if self.file_path.exists():
            with open(self.file_path) as f:
                return self.yaml.load(f) or CommentedMap()
        return CommentedMap()

    def save(self) -> None:
        """Save YAML data to file"""
        with open(self.file_path, "w") as f:
            self.yaml.dump(self.data, f)

    def _ensure_section(self, section: str) -> CommentedMap:
        """Ensure a section exists in the YAML"""
        if section not in self.data:
            self.data[section] = CommentedMap()
        return self.data[section]

    def update_key(self, key_name: str, key_path: str) -> None:
        """Add or update a key in the keys section"""
        keys = self._ensure_section("keys")

        if "key" in self.data:
            default_key = self.data["key"]
            keys["default"] = default_key
            del self.data["key"]

        keys[key_name] = key_path

    def update_environment(
        self,
        name: str,
        filepath: Optional[str] = None,
        watch: Optional[bool] = None,
        alias: Optional[list] = None,
        key: Optional[str] = None,
    ) -> None:
        """Add or update an environment"""
        envs = self._ensure_section("environments")
        if name not in envs:
            envs[name] = CommentedMap()

        env = envs[name]
        if filepath is not None:
            env["filepath"] = filepath
        if watch is not None:
            env["watch"] = watch
        if alias is not None:
            seq = CommentedSeq([str(a) for a in alias])
            seq.fa.set_flow_style()
            env["alias"] = seq
        if key is not None:
            env["key"] = key

    def update_variable(
        self,
        name: str,
        value: Any = None,
        key: Optional[str] = None,
        unencrypt: bool = False,
        environment: Optional[list] = None,
    ) -> None:
        """Add or update a variable"""
        from .places_utils import convert_string_value

        vars = self._ensure_section("variables")

        if isinstance(value, str):
            value = convert_string_value(value)

        if environment:
            if name not in vars:
                vars[name] = CommentedMap()
            var = vars[name]
            for env in environment:
                if env not in var:
                    var[env] = CommentedMap()
                env_data = var[env]
                env_data["value"] = value
                if key:
                    env_data["key"] = key
                if unencrypt:
                    env_data["unencrypted"] = True
        else:
            if key or unencrypt:
                vars[name] = CommentedMap()
                vars[name]["value"] = value
                if key:
                    vars[name]["key"] = key
                if unencrypt:
                    vars[name]["unencrypted"] = True
            else:
                vars[name] = value

    def update_settings(
        self,
        sync_gitignore: Optional[bool] = None,
        iterations: Optional[int] = None,
        hash_function: Optional[str] = None,
        salt_mode: Optional[str] = None,
        salt_filepath: Optional[str] = None,
        salt_value: Optional[str] = None,
    ) -> None:
        """Add or update settings"""
        settings = self._ensure_section("settings")

        if sync_gitignore is not None:
            settings["sync-gitignore"] = sync_gitignore

        if any([iterations, hash_function, salt_mode, salt_filepath, salt_value]):
            crypto = settings.setdefault("cryptography", CommentedMap())
            if iterations:
                crypto["iterations"] = iterations
            if hash_function:
                crypto["hash-function"] = hash_function

            if any([salt_mode, salt_filepath, salt_value]):
                salt = crypto.setdefault("salt", CommentedMap())
                if salt_mode:
                    salt["mode"] = salt_mode
                if salt_filepath:
                    salt["filepath"] = salt_filepath
                if salt_value:
                    salt["value"] = salt_value
