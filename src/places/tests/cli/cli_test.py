import os
import pytest
from filecmp import dircmp
from places.tests.conftest import run_command
from places.tests.test_utils import get_directory_differences


@pytest.mark.usefixtures("test_dirs")
def test_cli(test_dirs):
    temp_dir, expected_dir, original_dir = test_dirs

    # Change to temp directory and run commands
    os.chdir(temp_dir)

    try:
        # Run commands in sequence
        run_command("places init")

        # Add environments
        run_command("places add environment local -f .env -w true")
        run_command(
            "places add environment development -f .env.dev -k dev -a dev -a stage -w true"
        )
        run_command(
            "places add environment production -f .env.prod -k prod -a prod -w true"
        )

        # Add keys
        run_command("places add key_from_string default default -f -a")
        run_command("places add key_from_string dev dev -f -a")
        run_command("places add key_from_string prod prod -f -a")
        run_command("places add key_from_string test test -f -a")

        # Add settings
        run_command("places add setting -i 1")

        # Add variables
        run_command("places add variable PROJECT_NAME -v test-project")
        run_command("places add variable HOST -v localhost -u true")
        run_command("places add variable PORT -v 8000 -e local")
        run_command("places add variable PORT -v 8001 -e prod")
        run_command("places add variable PORT -v 8002 -e dev")
        run_command("places add variable ADDRESS -v '${HOST}:${PORT}'")
        run_command('places add variable KV -v \'{"key":"value"}\'')

        # Encrypt, decrypt and generate
        run_command("places encrypt")
        run_command("places decrypt")
        run_command("places generate environment --all")

    except Exception as e:
        print("\nTest failed during command execution:")
        print(str(e))
        raise

    # Compare directories
    comparison = dircmp(temp_dir, expected_dir)
    differences = get_directory_differences(comparison)

    # Create detailed error message if needed
    error_msg = []
    if differences["left_only"]:
        error_msg.append("Files only in temp: " + ", ".join(differences["left_only"]))
    if differences["right_only"]:
        error_msg.append(
            "Files only in expected_dir: " + ", ".join(differences["right_only"])
        )
    if differences["diff_files"]:
        error_msg.append("Different files: " + ", ".join(differences["diff_files"]))

    # Assert directories match
    assert not any(differences.values()), "\n".join(error_msg)