import click
import os
import importlib.resources
import places
from .decrypt import main as decrypt_main
from .encrypt import main as encrypt_main
from .generate_env import generate_env
from .generate_key import generate_key, add_key_to_places, validate_key_name
from .watch import start_watch, stop_watch
from .init import initialize_places
from .places_utils import error_exit
from .add_environment import add_environment_to_places, DEFAULT_YAML_PATH

# Define path constants
WORKING_DIR = os.getcwd()
PLACES_DIR = os.path.join(WORKING_DIR, ".places")
PLACES_YAML = os.path.join(WORKING_DIR, "places.yaml")
PLACES_LAYOUT = os.path.join(WORKING_DIR, ".places", "places.layout.yaml")
PLACES_ENC = os.path.join(WORKING_DIR, ".places", "places.enc.yaml")
PLACES_DEC = os.path.join(WORKING_DIR, ".places", "places.dec.yaml")
PLACES_SRC = importlib.resources.files(places)


@click.group()
def cli():
    """places - .envs for humans."""
    pass


def _decrypt():
    """Decrypt files in the project."""
    decrypt_main(source=PLACES_ENC, output=PLACES_YAML)


def _check_places_yaml():
    """Check if places.yaml exists, if not run decrypt."""
    if not os.path.exists(PLACES_YAML):
        print("places.yaml not found, running decrypt...")
        _decrypt()


def _encrypt():
    """Encrypt files in the project."""
    encrypt_main(source=PLACES_YAML, output=PLACES_ENC)


def _check_key_exists(name):
    """Check if key file exists in .places/keys directory."""
    key_path = os.path.join(PLACES_DIR, "keys", name)
    if not os.path.exists(key_path):
        raise click.UsageError(f"Key file '{name}' not found in .places/keys/")
    return True


@cli.group()
def generate():
    """Generate configurations for environments or keys."""
    pass


@cli.command()
def decrypt():
    """Decrypts ``.places/places.enc.yaml`` into ``places.yaml`` file."""
    _decrypt()


@cli.command()
def encrypt():
    """Encrypts ``places.yaml`` into ``.places/places.enc.yaml`` file."""
    _encrypt()


@generate.command()
@click.argument("environment", nargs=-1)
@click.option(
    "-a",
    "--all",
    "generate_all",
    is_flag=True,
    default=False,
    help="Generate .env files for all environments.",
)
def environment(environment, generate_all):
    """Generate .env files for specified environments or all environments defined in ``places.yaml``

    This generally follows https://dotenv-linter.github.io/ rules, with the exception of alphabetical ordering.

    """
    generate_env(environment=environment, generate_all=generate_all)


@generate.command()
@click.argument("name", type=click.STRING, default="default")
@click.option(
    "-l",
    "--length",
    type=click.INT,
    metavar="<Int>",
    default=32,
    help="Custom length for generated key in bytes.",
)
@click.option("-a", "--add", is_flag=True, help="Add key to places.yaml")
def key(name, length, add):
    """Generate a new encryption key with the specified name."""
    try:
        validate_key_name(name)
        generate_key(name, length=length, add_to_places=add)
    except Exception as e:
        click.echo(str(e), err=True)
        return


@cli.group()
def add():
    """Add configurations like keys."""
    pass


@add.command()
@click.argument("name", type=str)
@click.option("-a", "--add", is_flag=True, help="Add key reference to places.yaml")
def key(name, add):
    """Add an existing key file reference to places.yaml"""
    try:
        validate_key_name(name)
        if _check_key_exists(name) and add:
            add_key_to_places(name)
            print(f"Added reference to existing key '{name}' in places.yaml")
    except Exception as e:
        click.echo(str(e), err=True)
        return


@add.command(name="key_from_string")
@click.argument("name", type=str)
@click.argument("key_string", type=str)
@click.option("-a", "--add", is_flag=True, help="Add key to places.yaml")
@click.option(
    "-f",
    "--force-overwrite",
    is_flag=True,
    help="Force overwrite without safety checks.",
)
def from_string(name, key_string, add, force_overwrite):
    """Add a key from a provided string with the specified name."""
    generate_key(
        name, key=key_string, add_to_places=add, force_overwrite=force_overwrite
    )


@add.command()
@click.argument("name", type=str)
@click.option(
    "-f",
    "--filepath",
    type=click.STRING,
    metavar="<String>",
    help="Path to environment file.",
)
@click.option(
    "-w", "--watch", type=click.BOOL, metavar="<Bool>", help="Enable file watching."
)
@click.option(
    "-a", "--alias", multiple=True, metavar="<String>", help="Environment aliases."
)
@click.option(
    "-k",
    "--key",
    type=click.STRING,
    metavar="<String>",
    help="Key to use for encryption.",
)
def environment(name, filepath, watch, alias, key):
    """Add a new environment configuration."""
    processed_aliases = [a for a in alias] if alias else None
    add_environment_to_places(
        name,
        filepath=filepath,
        watch=watch,
        alias=processed_aliases,
        key=key,
        yaml_path=DEFAULT_YAML_PATH,
    )
    print(f"Added environment '{name}' to places.yaml")


@add.command()
@click.argument("name", type=click.STRING)
@click.option(
    "-v",
    "--value",
    type=click.STRING,
    metavar="<Any>",
    help="Value of variable / secret.",
)
@click.option(
    "-k",
    "--key",
    type=click.STRING,
    metavar="<String>",
    help="Key to use for encryption.",
)
@click.option(
    "-u",
    "--unencrypt",
    type=click.BOOL,
    metavar="<Bool>",
    help="Mark value as unencrypted.",
)
@click.option(
    "-e",
    "--environment",
    type=click.STRING,
    metavar="<String>",
    multiple=True,
    help="Target environment(s).",
)
def variable(name, value, key, unencrypt, environment):
    """Add a new variable configuration."""
    from .add_variable import add_variable_to_places

    env_list = list(environment) if environment else None
    add_variable_to_places(
        name, value=value, key=key, unencrypt=unencrypt, environment=env_list
    )
    print(f"Added variable '{name}' to places.yaml")


@add.command()
@click.option(
    "--sync-gitignore",
    "-sg",
    type=click.BOOL,
    metavar="<Bool>",
    help="Enable/disable .gitignore sync.",
)
@click.option(
    "--iterations",
    "-i",
    type=click.INT,
    metavar="<Int>",
    help="Number of iterations for cryptography.",
)
@click.option(
    "--hash-function",
    "-hf",
    type=click.STRING,
    metavar="<String>",
    help="Hash function for cryptography.",
)
@click.option(
    "--salt-mode",
    "-sm",
    type=click.STRING,
    metavar="<String>",
    help="Salt mode for cryptography.",
)
@click.option(
    "--salt-filepath",
    "-sf",
    type=click.STRING,
    metavar="<String>",
    help="Salt filepath for cryptography.",
)
@click.option(
    "--salt-value",
    "-sv",
    type=click.STRING,
    metavar="<String>",
    help="Salt value for cryptography.",
)
def setting(
    sync_gitignore, iterations, hash_function, salt_mode, salt_filepath, salt_value
):
    """Add or update settings configuration."""
    from .add_setting import add_setting_to_places

    add_setting_to_places(
        sync_gitignore=sync_gitignore,
        iterations=iterations,
        hash_function=hash_function,
        salt_mode=salt_mode,
        salt_filepath=salt_filepath,
        salt_value=salt_value,
    )
    print("Updated settings in places.yaml")


@cli.group()
def watch():
    """Watch for changes and automatically update."""
    pass


@watch.command()
@click.option(
    "-s",
    "--service",
    is_flag=True,
    default=False,
    help="Run watcher as a persistent system service.",
)
@click.option(
    "-d",
    "--daemon",
    is_flag=True,
    default=False,
    help="Run watcher as a background daemon.",
)
def start(service, daemon):
    """Start watching for changes."""
    _check_places_yaml()
    if service:
        start_watch(service=True)
    elif daemon:
        start_watch(daemon=True)
    else:
        start_watch()


@watch.command()
@click.option(
    "-s",
    "--service",
    is_flag=True,
    default=False,
    help="Stop and remove persistent system service.",
)
@click.option(
    "-d", "--daemon", is_flag=True, default=False, help="Stop daemon process."
)
def stop(service, daemon):
    """Stop watching for changes."""
    stop_watch(service=service, daemon=daemon)


@cli.group()
def sync():
    """Sync Places configurations."""
    pass


@sync.command()
def gitignore():
    """Sync .gitignore with Places entries."""


@cli.command()
@click.option(
    "--template",
    "-t",
    type=click.STRING,
    metavar="<String>",
    help="Template to use for initialization",
)
@click.option("--list-templates", is_flag=True, help="List available templates")
def init(template, list_templates):
    """Initialize a new places project.

    Also generates a new default encryption key and adds it to ``.places/keys/``.
    """
    if list_templates:
        initialize_places(list_templates=True)
        return

    initialize_places(template_name=template)
    if template:
        _encrypt()


@cli.group()
def run():
    """Run various Places commands."""
    pass


@run.command()
@click.argument("tests", nargs=-1)
@click.option("--all", "-a", "run_all", is_flag=True, help="Run all tests.")
def test(tests, run_all):
    """Run tests.

    Currently supported tests: e2e, cli.

    Specify test names or use --all flag."""

    try:
        import pytest
    except ImportError:
        error_exit(
            "pytest is required for running tests. Install it with: pip install pytest"
        )

    if not tests and not run_all:
        click.echo("Please specify tests to run or use --all flag", err=True)
        return

    test_args = []
    test_paths = []

    if "e2e" in tests or run_all:
        print(PLACES_SRC)
        test_path = os.path.join(PLACES_SRC, "tests/e2e/e2e_test.py")
        test_paths.append(test_path)
    if "cli" in tests or run_all:
        test_path = os.path.join(PLACES_SRC, "tests/cli/cli_test.py")
        test_paths.append(test_path)

    if not test_paths:
        click.echo("No valid tests specified", err=True)
        return

    test_args.extend(["-v", "-p", "no:warnings"])
    test_args.extend(test_paths)

    exit_code = pytest.main(test_args)
    if exit_code != 0:
        click.echo("Some tests failed", err=True)
        exit(exit_code)


if __name__ == "__main__":
    cli()
