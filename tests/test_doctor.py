"""scripts/doctor.py and the repo-root-relative database path (audit F-12)."""
import importlib.util
import os

import chromadb
import pytest

import config

HERE = os.path.dirname(__file__)
spec = importlib.util.spec_from_file_location("doctor", os.path.join(HERE, "..", "scripts", "doctor.py"))
doctor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doctor)


def make_store(path, n):
    client = chromadb.PersistentClient(path=str(path))
    coll = client.get_or_create_collection("nyaymitra_legal", metadata={"hnsw:space": "cosine"})
    if n:
        coll.add(ids=[f"c{i}" for i in range(n)], documents=["x"] * n,
                 embeddings=[[1.0, 0.0]] * n, metadatas=[{"domain": "d"}] * n)


# --- path resolution ------------------------------------------------------------
def test_relative_database_path_is_resolved_against_the_repo_root_not_the_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = os.path.abspath(os.sep + "some" + os.sep + "repo")
    assert config._resolve_path("chromadb_store", root=root) == os.path.join(root, "chromadb_store")


def test_absolute_database_path_is_used_as_given(tmp_path):
    assert config._resolve_path(str(tmp_path), root="/ignored") == str(tmp_path)


def test_the_configured_path_is_always_absolute():
    assert os.path.isabs(config.CHROMADB_PATH)


# --- doctor -----------------------------------------------------------------------
def test_doctor_reports_ok_when_the_active_store_has_data(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    make_store(root / "chromadb_store", 3)
    r = doctor.diagnose(str(root), {})
    assert r["verdict"].startswith("OK") and r["source"] == "default"
    assert r["stores"][str(root / "chromadb_store")] == [("nyaymitra_legal", 3)]


def test_doctor_catches_the_wrong_path_case_where_data_lives_elsewhere(tmp_path):
    """The real incident: the app pointed at a folder with a stray name while the data was intact."""
    root = tmp_path / "repo"
    root.mkdir()
    make_store(root / "chromadb_store", 174)
    r = doctor.diagnose(str(root), {"CHROMADB_PATH": "./chromadb_storecd backend"})
    assert r["verdict"].startswith("PROBLEM") and "chromadb_store" in r["verdict"]
    assert r["source"] == "process environment variable" and not r["active_exists"]


def test_doctor_never_creates_a_store(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    r = doctor.diagnose(str(root), {"CHROMADB_PATH": "nowhere"})
    assert r["verdict"].startswith("EMPTY") and not (root / "nowhere").exists()


def test_process_environment_overrides_dotenv_like_python_dotenv(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".env").write_text("CHROMADB_PATH=from_dotenv\n", encoding="utf-8")
    assert doctor.diagnose(str(root), {})["source"].startswith(".env file")
    assert doctor.diagnose(str(root), {"CHROMADB_PATH": "from_env"})["raw"] == "from_env"


def test_secrets_in_dotenv_are_never_shown(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".env").write_text(
        "SARVAM_API_KEY=sk-super-secret\nGROQ_API_KEY=gsk-also-secret\nCHROMADB_PATH=chromadb_store\n"
        "ROUTING_MODE=none\n", encoding="utf-8")
    text = doctor.format_report(doctor.diagnose(str(root), {}))
    assert "sk-super-secret" not in text and "gsk-also-secret" not in text
    assert "SARVAM_API_KEY" not in text
    assert "CHROMADB_PATH=chromadb_store" in text and "ROUTING_MODE=none" in text
    assert "2 other setting(s) not shown" in text


def test_a_dotenv_in_a_parent_folder_is_reported_because_python_dotenv_would_load_it(tmp_path):
    root = tmp_path / "dev" / "repo"
    root.mkdir(parents=True)
    (tmp_path / "dev" / ".env").write_text("CHROMADB_PATH=weird\n", encoding="utf-8")
    assert str(tmp_path / "dev" / ".env") in doctor.find_dotenv_files(str(root))


def test_empty_store_with_no_data_anywhere_says_to_run_the_loader(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    make_store(root / "chromadb_store", 0)
    assert "load_chromadb" in doctor.diagnose(str(root), {})["verdict"]


# --- the doctor must be read-only ----------------------------------------------------
def _snapshot(folder):
    import hashlib
    snap = {}
    for dirpath, _, files in os.walk(folder):
        for f in files:
            full = os.path.join(dirpath, f)
            with open(full, "rb") as fh:
                snap[os.path.relpath(full, folder)] = hashlib.sha256(fh.read()).hexdigest()
    return snap


def test_inspecting_a_store_changes_not_a_single_byte(tmp_path):
    store = tmp_path / "chromadb_store"
    make_store(store, 5)
    before = _snapshot(store)
    assert doctor.inspect_store(str(store)) == [("nyaymitra_legal", 5)]
    assert _snapshot(store) == before


def test_the_full_report_leaves_every_store_untouched(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    make_store(root / "chromadb_store", 4)
    make_store(root / "scripts" / "chromadb_storecd backend", 2)
    before = _snapshot(root)
    doctor.format_report(doctor.diagnose(str(root), {"CHROMADB_PATH": "./chromadb_storecd backend"}))
    assert _snapshot(root) == before


def test_deleted_chunks_are_not_counted(tmp_path):
    store = tmp_path / "s"
    make_store(store, 5)
    client = chromadb.PersistentClient(path=str(store))
    client.get_collection("nyaymitra_legal").delete(ids=["c0", "c1"])
    del client
    assert doctor.inspect_store(str(store)) == [("nyaymitra_legal", 3)]


def test_an_unreadable_database_is_reported_not_raised(tmp_path):
    store = tmp_path / "broken"
    store.mkdir()
    (store / "chroma.sqlite3").write_bytes(b"this is not a sqlite database")
    result = doctor.inspect_store(str(store))
    assert isinstance(result, str) and "could not read" in result


def test_no_temporary_copies_are_left_behind(tmp_path):
    import tempfile
    store = tmp_path / "s"
    make_store(store, 1)
    before = {d for d in os.listdir(tempfile.gettempdir()) if d.startswith("doctor_")}
    doctor.inspect_store(str(store))
    after = {d for d in os.listdir(tempfile.gettempdir()) if d.startswith("doctor_")}
    assert after == before
