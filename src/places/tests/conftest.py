from typing import Dict, List, Tuple
from filecmp import dircmp
from pathlib import Path
import os
import pytest
import shutil
import subprocess
from subprocess import CompletedProcess
import tempfile


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    """Store test results on the item for use in fixtures."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


def get_directory_differences(dcmp: dircmp) -> Dict[str, List[str]]:
    """
    Recursively collect differences between two directories.
    Returns a dictionary containing lists of left_only, right_only, and diff_files.
    """
    differences = {"left_only": [], "right_only": [], "diff_files": []}

    def collect_differences(dcmp: dircmp, path: str = "") -> None:
        current_path = f"{path}/" if path else ""
        differences["left_only"].extend(f"{current_path}{x}" for x in dcmp.left_only)
        differences["right_only"].extend(f"{current_path}{x}" for x in dcmp.right_only)
        differences["diff_files"].extend(f"{current_path}{x}" for x in dcmp.diff_files)
        for name, sub_dcmp in dcmp.subdirs.items():
            collect_differences(sub_dcmp, f"{current_path}{name}")

    collect_differences(dcmp)
    return differences


def run_command(cmd: str) -> str:
    """
    Run a shell command and return its output.
    Raises subprocess.CalledProcessError if the command fails.
    """
    try:
        result: CompletedProcess = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"\nCommand '{cmd}' failed:")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        raise


@pytest.fixture
def test_dirs(request: pytest.FixtureRequest):
    """
    Fixture providing temporary and expected test directories.
    Returns (temp_dir, expected_dir, original_dir) paths.
    """
    original_dir = os.getcwd()
    current_dir = Path(request.module.__file__).parent
    expected_dir = current_dir / "expected_dir"

    with tempfile.TemporaryDirectory() as temp_root:
        temp_dir = Path(temp_root) / "temp"
        reference_dir = Path(temp_root) / "reference"
        os.makedirs(temp_dir)
        os.makedirs(reference_dir)

        # Always copy expected files if they exist
        if expected_dir.exists():
            shutil.copytree(expected_dir, reference_dir, dirs_exist_ok=True)
        
        yield str(temp_dir), str(reference_dir), original_dir

        # Change back to original directory
        os.chdir(original_dir)
