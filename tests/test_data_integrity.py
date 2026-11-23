"""Checks the legal knowledge base files and their agreement with config."""
import glob
import json
import os
from collections import Counter

import pytest

from config import DATA_DIR, DOMAINS

REQUIRED_META = {"domain", "jurisdiction", "language", "source", "type"}


def _load(domain):
    path = os.path.join(DATA_DIR, domain, f"{domain}_chromadb_chunks.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize("domain", DOMAINS)
def test_every_configured_domain_has_a_chunks_file(domain):
    assert _load(domain), f"no chunks for {domain}"


@pytest.mark.parametrize("domain", DOMAINS)
def test_chunks_have_required_fields(domain):
    for chunk in _load(domain):
        assert {"id", "text", "metadata"} <= set(chunk)
        assert chunk["text"].strip()
        missing = REQUIRED_META - set(chunk["metadata"])
        assert not missing, f"{chunk['id']} missing {missing}"


def test_chunk_ids_are_unique_across_all_domains():
    ids = Counter(c["id"] for d in DOMAINS for c in _load(d))
    assert [i for i, n in ids.items() if n > 1] == []


@pytest.mark.parametrize("domain", DOMAINS)
def test_retrieval_filter_value_matches_stored_metadata(domain):
    """F-03: the value used in the Chroma `where` filter must exist in the data."""
    from rag_pipeline import chroma_domain_value

    stored = {c["metadata"]["domain"] for c in _load(domain)}
    assert chroma_domain_value(domain) in stored


def test_only_folder_chunk_files_are_loaded():
    """Documents the stray root-level women_safety file (audit F-09): it is not
    read by the loader, so it must not be mistaken for live data."""
    stray = os.path.join(DATA_DIR, "women_safety_chromadb_chunks.json")
    if os.path.exists(stray):
        loaded = {os.path.normpath(p) for p in glob.glob(os.path.join(DATA_DIR, "*", "*_chromadb_chunks.json"))}
        assert os.path.normpath(stray) not in loaded
