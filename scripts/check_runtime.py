"""Check pinned runtime packages without importing or installing them."""
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import sys


def missing_requirements(path):
    missing = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, expected = line.split("==", 1)
        try:
            installed = version(name)
        except PackageNotFoundError:
            installed = None
        if installed != expected:
            missing.append(line)
    return missing


if __name__ == "__main__":
    needed = missing_requirements(Path(__file__).resolve().parent.parent / "requirements.txt")
    if needed:
        print("Runtime setup needed: " + ", ".join(needed))
    sys.exit(bool(needed))
