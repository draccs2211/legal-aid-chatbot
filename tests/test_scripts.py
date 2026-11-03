"""The helper scripts must at least import cleanly (audit F-11)."""
import importlib.util
import os

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "scripts")


def _load(name):
    spec = importlib.util.spec_from_file_location(
        "script_under_test_" + name, os.path.join(SCRIPTS, name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # runs top-level imports, not main()
    return module


def test_test_rag_script_imports_without_repo_root_on_path():
    mod = _load("test_rag")
    assert callable(mod.main)


def test_distance_formatting_handles_float_and_missing_values():
    mod = _load("test_rag")
    assert mod.format_distance(0.123456) == "0.1235"
    assert mod.format_distance(None) == "None"
    assert mod.format_distance("N/A") == "N/A"
