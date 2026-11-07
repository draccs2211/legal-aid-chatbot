"""Keeps .env.example honest."""
import glob
import os
import re

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _example_keys():
    keys = {}
    for line in _read(os.path.join(ROOT, ".env.example")).splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            keys[k.strip()] = v.strip()
    return keys


def _variables_read_by_the_backend():
    names = set()
    for path in glob.glob(os.path.join(ROOT, "backend", "*.py")):
        names |= set(re.findall(r'(?:getenv|_choice)\(\s*"([A-Z][A-Z0-9_]+)"', _read(path)))
    return names


def test_every_variable_the_backend_reads_is_documented():
    missing = _variables_read_by_the_backend() - set(_example_keys())
    assert missing == set(), f"add these to .env.example: {sorted(missing)}"


def test_the_example_contains_no_secrets():
    for key, value in _example_keys().items():
        if key.endswith("_KEY") or "SECRET" in key or "TOKEN" in key:
            assert value == "", f"{key} must be empty in .env.example"


def test_the_example_database_path_is_exactly_the_default_with_nothing_appended():
    assert _example_keys()["CHROMADB_PATH"] == "./chromadb_store"


def test_dotenv_is_ignored_by_git_so_secrets_cannot_be_committed():
    """Asks git itself, so any valid .gitignore pattern counts. Skipped outside a
    repo that has a .gitignore (for example an unpacked archive)."""
    import shutil
    import subprocess

    import pytest

    if not os.path.exists(os.path.join(ROOT, ".gitignore")) or shutil.which("git") is None:
        pytest.skip("no .gitignore or no git available")
    result = subprocess.run(["git", "check-ignore", "-q", ".env"], cwd=ROOT)
    if result.returncode == 128:
        pytest.skip("not a git repository")
    assert result.returncode == 0, "'.env' is NOT ignored by git: add a line '.env' to .gitignore"
