"""Portable checks for the Windows launcher's dependency preflight."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from importlib.metadata import PackageNotFoundError
from scripts.check_runtime import missing_requirements


class RuntimeSetupTests(unittest.TestCase):
    def check(self, installed):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "requirements.txt"
            path.write_text("# runtime\n\nFlask==3.1.3\n", encoding="utf-8")
            with patch("scripts.check_runtime.version", **installed):
                return missing_requirements(path)

    def test_matching_install_needs_no_network_repair(self):
        self.assertEqual(self.check({"return_value": "3.1.3"}), [])

    def test_missing_package_requires_repair(self):
        self.assertEqual(self.check({"side_effect": PackageNotFoundError("Flask")}), ["Flask==3.1.3"])

    def test_wrong_version_requires_repair(self):
        self.assertEqual(self.check({"return_value": "3.0.0"}), ["Flask==3.1.3"])
