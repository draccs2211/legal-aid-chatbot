"""Safe diagnostics for "the database looks empty" and similar surprises.

    python scripts/doctor.py

Prints the effective ChromaDB path and where it came from, every .env file that
could be loaded, and every Chroma store found under the repository with its
chunk count. It never prints a secret: from .env files it shows only keys that
start with CHROMADB_, COLLECTION_, EMBEDDING_ or ROUTING_, and counts the rest.
It never creates a store: stores are opened only if they already exist.
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "backend"))

SAFE_PREFIXES = ("CHROMADB_", "COLLECTION_", "EMBEDDING_", "ROUTING_")
SKIP_DIRS = {".venv", "venv", ".git", "node_modules", "__pycache__", ".pytest_cache"}
DEFAULT_PATH = "chromadb_store"


def _walk(root, max_depth):
    root = os.path.abspath(root)
    base_depth = root.rstrip(os.sep).count(os.sep)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        if dirpath.rstrip(os.sep).count(os.sep) - base_depth >= max_depth:
            dirnames[:] = []
        yield dirpath, filenames


def find_dotenv_files(root, max_depth=3):
    """Every .env under the repo, plus any in the parent folders python-dotenv would also search."""
    found = [os.path.join(d, ".env") for d, files in _walk(root, max_depth) if ".env" in files]
    parent = os.path.dirname(os.path.abspath(root))
    while True:
        candidate = os.path.join(parent, ".env")
        if os.path.isfile(candidate):
            found.append(candidate)
        nxt = os.path.dirname(parent)
        if nxt == parent:
            break
        parent = nxt
    return sorted(set(found))


def read_dotenv_safe(path):
    """(visible, hidden_count): values only for non-secret key prefixes."""
    visible, hidden = {}, 0
    try:
        with open(path, encoding="utf-8-sig") as f:
            lines = f.read().splitlines()
    except OSError:
        return {}, 0
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().removeprefix("export ").strip()
        if key.startswith(SAFE_PREFIXES):
            visible[key] = value.strip().strip('"').strip("'")
        else:
            hidden += 1
    return visible, hidden


def find_stores(root, max_depth=3):
    return sorted(d for d, files in _walk(root, max_depth) if "chroma.sqlite3" in files)


def inspect_store(path):
    """[(collection, count)] for an EXISTING store, or an error string."""
    if not os.path.isfile(os.path.join(path, "chroma.sqlite3")):
        return []
    try:
        import chromadb
        client = chromadb.PersistentClient(path=path)
        return [(c.name, c.count()) for c in client.list_collections()]
    except Exception as e:  # pragma: no cover - depends on the installed chromadb
        return f"could not open: {type(e).__name__}: {e}"


def effective_path(environ, dotenv_files, root):
    """(raw value, source, absolute path) following python-dotenv's rule:
    the process environment wins over .env files."""
    if "CHROMADB_PATH" in environ:
        raw, source = environ["CHROMADB_PATH"], "process environment variable"
    else:
        raw, source = DEFAULT_PATH, "default"
        for f in dotenv_files:
            visible, _ = read_dotenv_safe(f)
            if "CHROMADB_PATH" in visible:
                raw, source = visible["CHROMADB_PATH"], f".env file {f}"
                break
    absolute = raw if os.path.isabs(raw) else os.path.normpath(os.path.join(root, raw))
    return raw, source, absolute


def diagnose(root, environ):
    dotenvs = find_dotenv_files(root)
    raw, source, active = effective_path(environ, dotenvs, root)
    stores = find_stores(root)
    if os.path.isfile(os.path.join(active, "chroma.sqlite3")) and active not in stores:
        stores.append(active)
    report = {
        "root": os.path.abspath(root), "raw": raw, "source": source, "active": active,
        "active_exists": os.path.isdir(active),
        "active_has_store": os.path.isfile(os.path.join(active, "chroma.sqlite3")),
        "dotenv": {f: read_dotenv_safe(f) for f in dotenvs},
        "stores": {s: inspect_store(s) for s in stores},
    }
    active_counts = report["stores"].get(active, [])
    has_data = isinstance(active_counts, list) and any(n > 0 for _, n in active_counts)
    others = [s for s, c in report["stores"].items()
              if s != active and isinstance(c, list) and any(n > 0 for _, n in c)]
    if has_data:
        report["verdict"] = "OK: the active store contains data."
    elif others:
        report["verdict"] = ("PROBLEM: the app points at a store with no data, but data exists elsewhere: "
                             + "; ".join(others) + ". Fix CHROMADB_PATH (see 'source' above).")
    else:
        report["verdict"] = "EMPTY: no store with data was found. Run: python scripts/load_chromadb.py"
    return report


def format_report(r):
    out = [f"Repo root: {r['root']}",
           f"CHROMADB_PATH = {r['raw']!r}   (from {r['source']})",
           f"  resolves to: {r['active']}",
           f"  folder exists: {r['active_exists']}, has chroma.sqlite3: {r['active_has_store']}", "",
           ".env files that can be loaded:"]
    if not r["dotenv"]:
        out.append("  (none)")
    for path, (visible, hidden) in r["dotenv"].items():
        out.append(f"  {path}")
        for k, v in visible.items():
            out.append(f"      {k}={v}")
        out.append(f"      ({hidden} other setting(s) not shown)")
    out += ["", "Chroma stores found:"]
    if not r["stores"]:
        out.append("  (none)")
    for path, cols in r["stores"].items():
        mark = "   <-- ACTIVE" if path == r["active"] else ""
        desc = cols if isinstance(cols, str) else ", ".join(f"{n}: {c} chunks" for n, c in cols) or "no collections"
        out.append(f"  {path}{mark}\n      {desc}")
    out += ["", r["verdict"]]
    return "\n".join(out)


if __name__ == "__main__":
    print(format_report(diagnose(ROOT, os.environ)))
