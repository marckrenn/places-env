from typing import Dict, List, Tuple
from filecmp import dircmp
from pathlib import Path
import os
import pytest
import shutil
import subprocess
from subprocess import CompletedProcess


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


def setup_test_directories(base_dir: Path) -> Tuple[Path, Path]:
    """Set up temporary and expected test directories."""
    temp_dir = base_dir / "temp"
    expected_dir = base_dir / "expected_dir"

    os.makedirs(temp_dir.parent, exist_ok=True)
    os.makedirs(expected_dir, exist_ok=True)

    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)

    return temp_dir, expected_dir


@pytest.fixture
def test_dirs(request: pytest.FixtureRequest) -> Tuple[str, str, str]:
    """
    Fixture providing temporary and expected test directories.
    Returns (temp_dir, expected_dir, original_dir) paths.
    """
    current_dir = Path(request.module.__file__).parent
    temp_dir, expected_dir = setup_test_directories(current_dir)

    is_reference_empty = not expected_dir.exists() or not any(expected_dir.iterdir())
    original_dir = os.getcwd()

    def cleanup() -> None:
        os.chdir(original_dir)

        rep_call = getattr(request.node, "rep_call", None)
        rep_setup = getattr(request.node, "rep_setup", None)
        test_failed = (rep_call and not rep_call.passed) or (
            rep_setup and not rep_setup.passed
        )

        if is_reference_empty and not test_failed:
            print(f"\nCreating reference files in: {expected_dir}")
            if expected_dir.exists():
                shutil.rmtree(expected_dir)
            shutil.copytree(temp_dir, expected_dir)

        if temp_dir.exists() and not test_failed:
            shutil.rmtree(temp_dir)
        elif test_failed:
            print(f"\nTest failed - Keeping temp directory for inspection: {temp_dir}")

    request.addfinalizer(cleanup)

    return str(temp_dir), str(expected_dir), original_dir
