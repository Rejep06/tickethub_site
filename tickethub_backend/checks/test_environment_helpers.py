"""Offline helper tests. These do NOT run Django or PostgreSQL."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


env = load_module("tickethub_env", ROOT / "backend/config/env.py")
setup = load_module("tickethub_setup", ROOT / "scripts/create_local_env.py")


class EnvironmentReaderTests(unittest.TestCase):
    def test_bool_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(env.env_bool("FLAG"))
            self.assertTrue(env.env_bool("FLAG", True))

    def test_bool_true_values(self):
        for value in ("true", "1", "yes", " TRUE "):
            with self.subTest(value=value), patch.dict(os.environ, {"FLAG": value}):
                self.assertTrue(env.env_bool("FLAG"))

    def test_bool_false_values(self):
        for value in ("false", "0", "no", " FALSE "):
            with self.subTest(value=value), patch.dict(os.environ, {"FLAG": value}):
                self.assertFalse(env.env_bool("FLAG", True))

    def test_bool_invalid_fails_closed(self):
        with patch.dict(os.environ, {"FLAG": "enabled"}):
            with self.assertRaises(ValueError):
                env.env_bool("FLAG")

    def test_empty_value_uses_default(self):
        with patch.dict(os.environ, {"FLAG": "", "PORT": ""}):
            self.assertTrue(env.env_bool("FLAG", True))
            self.assertEqual(env.env_int("PORT", 5432), 5432)

    def test_list_trims_and_drops_empty_items(self):
        with patch.dict(os.environ, {"HOSTS": " localhost, ,example.test "}):
            self.assertEqual(env.env_list("HOSTS"), ["localhost", "example.test"])

    def test_integer_minimum(self):
        with patch.dict(os.environ, {"PORT": "0"}):
            with self.assertRaises(ValueError):
                env.env_int("PORT", 5432, minimum=1)

    def test_integer_valid(self):
        with patch.dict(os.environ, {"PORT": " 5433 "}):
            self.assertEqual(env.env_int("PORT", 5432), 5433)


class LocalSetupTests(unittest.TestCase):
    def test_creates_nonempty_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / ".env"
            setup.create_env(destination)
            values = dict(line.split("=", 1) for line in destination.read_text().splitlines() if line and not line.startswith("#"))
            self.assertGreaterEqual(len(values["DJANGO_SECRET_KEY"]), 50)
            self.assertGreaterEqual(len(values["POSTGRES_PASSWORD"]), 32)
            self.assertEqual(values["EMAIL_HOST_PASSWORD"], "")

    def test_does_not_overwrite_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / ".env"
            destination.write_text("keep-this-content")
            with self.assertRaises(FileExistsError):
                setup.create_env(destination)
            self.assertEqual(destination.read_text(), "keep-this-content")

    def test_random_secrets_differ(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory) / "a", Path(directory) / "b"
            setup.create_env(a)
            setup.create_env(b)
            self.assertNotEqual(a.read_text(), b.read_text())

    @unittest.skipUnless(os.name == "posix", "POSIX file modes only")
    def test_private_file_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / ".env"
            setup.create_env(destination)
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
