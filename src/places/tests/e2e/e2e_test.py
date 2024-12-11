import os
import pytest
from filecmp import dircmp
from places.tests.conftest import run_command
from places.tests.test_utils import get_directory_differences


@pytest.mark.usefixtures("test_dirs")
def test_e2e(test_dirs):
    temp_dir, expected_dir, original_dir = test_dirs

    # Change to temp directory and run commands
    os.chdir(temp_dir)

    try:
        # Run each command and capture output
        run_command("uv run places init")  # Initialize with empty configuration first
        run_command("uv run places add key_from_string default default -f")
        run_command("uv run places add key_from_string prod prod -f")
        run_command("uv run places add key_from_string dev dev -f")
        run_command("uv run places add key_from_string test test -f")
        run_command(
            "uv run places init --template _e2e_test"
        )  # Re-initialize with e2e_test template (a bit hacky, I know)
        run_command("uv run places encrypt")
        run_command("uv run places decrypt")
        run_command("uv run places generate environment --all")
    except Exception as e:
        print("\nTest failed during command execution:")
        print(str(e))
        raise
    finally:
        os.chdir(original_dir)

    # Compare only specific files we care about
    ignore = ['expected_dir', '.pytest_cache', '__pycache__', '.gitignore']
    comparison = dircmp(temp_dir, expected_dir, ignore=ignore)
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
