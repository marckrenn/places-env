from filecmp import dircmp
from pathlib import Path
from typing import Dict, List


def get_directory_differences(comparison: dircmp) -> Dict[str, List[str]]:
    """
    Collects all differences between two directories recursively.

    Args:
        comparison: A dircmp object containing directory comparison results

    Returns:
        Dict with 'left_only', 'right_only', and 'diff_files' listings
    """
    differences = {"left_only": [], "right_only": [], "diff_files": []}

    def collect_differences(dcmp: dircmp, base_path: Path = Path()):
        differences["left_only"].extend(str(base_path / x) for x in dcmp.left_only)
        differences["right_only"].extend(str(base_path / x) for x in dcmp.right_only)
        differences["diff_files"].extend(str(base_path / x) for x in dcmp.diff_files)

        for name, sub_dcmp in dcmp.subdirs.items():
            collect_differences(sub_dcmp, base_path / name)

    collect_differences(comparison)
    return differences
