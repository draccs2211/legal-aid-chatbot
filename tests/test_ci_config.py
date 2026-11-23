"""Keeps the CI setup honest: it must run the tests, need no secrets, and install
everything the backend imports at start-up."""
import ast
import glob
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "tests.yml")
CI_REQS = os.path.join(ROOT, "requirements-ci.txt")

# import name -> distribution that provides it (only where they differ or are transitive)
PROVIDED_BY = {"dotenv": "python-dotenv", "multipart": "python-multipart",
               "pydantic": "fastapi", "starlette": "fastapi"}


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _ci_packages():
    names = set()
    for line in _read(CI_REQS).splitlines():
        line = line.split("#")[0].strip()
        if line:
            names.add(line.split("==")[0].split(">=")[0].strip().lower())
    return names


def _toplevel_third_party_imports(path):
    tree = ast.parse(_read(path))
    local = {os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(ROOT, "backend", "*.py"))}
    found = set()
    for node in tree.body:  # module level only: lazy imports inside functions are optional
        if isinstance(node, ast.Import):
            found |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module.split(".")[0])
    return {m for m in found if m not in sys.stdlib_module_names and m not in local}


def test_workflow_runs_pytest_and_installs_the_ci_requirements():
    text = _read(WORKFLOW)
    assert "python -m pytest" in text and "requirements-ci.txt" in text
    assert "pull_request" in text and "push" in text


def test_workflow_needs_no_secrets():
    assert "secrets." not in _read(WORKFLOW)


def test_ci_requirements_leave_out_the_heavy_model_stack():
    packages = _ci_packages()
    assert not {"torch", "sentence-transformers", "transformers"} & packages


def test_every_module_level_import_in_the_backend_is_installed_in_ci():
    needed = set()
    for path in glob.glob(os.path.join(ROOT, "backend", "*.py")):
        needed |= _toplevel_third_party_imports(path)
    missing = {m for m in needed if PROVIDED_BY.get(m, m).lower().replace("_", "-") not in _ci_packages()}
    assert missing == set(), f"add to requirements-ci.txt: {sorted(missing)}"
