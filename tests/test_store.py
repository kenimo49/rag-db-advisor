"""AdvisorStore fail-closed behavior — no network, no real embeddings.

The store's contract is "evidence integrity is the product": every failure
mode must surface as an explicit error, never as a silently wrong answer.
"""

import json

import numpy as np
import pytest

from rag_db_advisor.store import EMBED_DIM, AdvisorStore, default_home


class FakeRetriever:
    """Stands in for the chroma backend so tests run offline and fast."""

    def __init__(self, search_result=None):
        self.search_result = search_result or []
        self.loaded_ids = None
        self.searched_k = None

    def setup(self, dim):
        pass

    def load(self, ids, texts, vecs):
        self.loaded_ids = list(ids)

    def build_index(self):
        pass

    def search(self, vec, k):
        self.searched_k = k
        return self.search_result[:k]


def _store(tmp_path, monkeypatch, search_result=None):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    store = AdvisorStore.__new__(AdvisorStore)
    store.home = tmp_path
    store.chunks_path = tmp_path / "chunks.json"
    store.retriever = FakeRetriever(search_result)
    store._chunks = None
    store._openai = None
    monkeypatch.setattr(store, "_embed", lambda texts: np.zeros((len(texts), EMBED_DIM), dtype=np.float32))
    return store


def _write_manifest(store, ids):
    store.chunks_path.write_text(
        json.dumps({i: {"id": i, "text": f"body of {i}"} for i in ids}),
        encoding="utf-8",
    )


def test_missing_api_key_fails_before_anything_else(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    monkeypatch.delenv("OPENAI_API_KEY")
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        store.retrieve("which db?")


def test_empty_store_tells_user_to_ingest(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    with pytest.raises(RuntimeError, match="run `rag-db-advisor ingest`"):
        store.retrieve("which db?")


def test_unknown_id_fails_closed(tmp_path, monkeypatch):
    # Vector store returns an id the manifest doesn't know -> the two are out
    # of sync. Must raise, not skip: a partial answer would look authoritative.
    store = _store(tmp_path, monkeypatch, search_result=["note:ghost#9"])
    _write_manifest(store, ["note:pgvector#0"])
    with pytest.raises(RuntimeError, match="store/chunks mismatch"):
        store.retrieve("which db?")


def test_empty_search_result_fails_closed(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch, search_result=[])
    _write_manifest(store, ["note:pgvector#0"])
    with pytest.raises(RuntimeError, match="no results"):
        store.retrieve("which db?")


def test_happy_path_returns_manifest_chunks(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch, search_result=["note:pgvector#0"])
    _write_manifest(store, ["note:pgvector#0"])
    out = store.retrieve("which db?", top_k=1)
    assert out == [{"id": "note:pgvector#0", "text": "body of note:pgvector#0"}]


def test_top_k_clamped_to_corpus_size(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch, search_result=["a", "b"])
    _write_manifest(store, ["a", "b"])
    store.retrieve("q", top_k=999)
    assert store.retriever.searched_k == 2
    store._chunks = None
    store.retrieve("q", top_k=0)
    assert store.retriever.searched_k == 1


def test_ingest_writes_manifest_atomically(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    n = store.ingest()
    assert n > 0
    manifest = json.loads(store.chunks_path.read_text(encoding="utf-8"))
    assert len(manifest) == n
    assert store.retriever.loaded_ids == list(manifest.keys())
    assert not store.chunks_path.with_suffix(".json.tmp").exists()


def test_ingest_invalidates_manifest_before_rebuild(tmp_path, monkeypatch):
    # Once the destructive rebuild starts (collection dropped), the old
    # manifest must already be gone: "broken and loud" beats "stale and
    # plausible". An earlier embed failure leaves the old store untouched.
    store = _store(tmp_path, monkeypatch)
    _write_manifest(store, ["stale"])

    def boom(dim):
        raise RuntimeError("setup exploded")

    store.retriever.setup = boom
    with pytest.raises(RuntimeError, match="setup exploded"):
        store.ingest()
    assert not store.chunks_path.exists()


def test_default_home_respects_env(monkeypatch, tmp_path):
    monkeypatch.setenv("RAG_DB_ADVISOR_HOME", str(tmp_path / "custom"))
    assert default_home() == tmp_path / "custom"
