"""MCP tool behavior — bundled measurement data, no store, no network.

FastMCP's @tool() returns the plain function, so tools are called directly.
"""

from rag_db_advisor import mcp_server


class FakeStore:
    def __init__(self, evidence=None, error=None):
        self.evidence = evidence or []
        self.error = error

    def retrieve(self, question, top_k):
        if self.error:
            raise RuntimeError(self.error)
        return self.evidence[:top_k]


def test_advise_returns_evidence_and_guardrail_note(monkeypatch):
    chunk = {"id": "note:pgvector#0", "text": "...", "source": "knowledge/ja/pgvector.md"}
    monkeypatch.setattr(mcp_server, "_store", FakeStore(evidence=[chunk]))
    out = mcp_server.advise("10万件ならどれ?")
    assert out["evidence"] == [chunk]
    assert "evidence にない数値は引用しない" in out["note"]


def test_advise_converts_store_errors_to_payload(monkeypatch):
    # MCP tools must not raise through the protocol: error -> {"error", "hint"}
    monkeypatch.setattr(mcp_server, "_store", FakeStore(error="store is empty"))
    out = mcp_server.advise("q")
    assert out["error"] == "store is empty"
    assert "ingest" in out["hint"]


def test_compare_backends_splits_server_and_embedded():
    out = mcp_server.compare_backends(corpus_size=100000)
    server = out["server_backends"]
    embedded = out["embedded_backends"]
    assert server and embedded
    assert all("embedded" not in str(r["mode"]) for r in server)
    assert all("embedded" in str(r["mode"]) for r in embedded)
    # embedded backends must never be ranked against server ones
    assert "直接比較不可" in out["caveat"]


def test_compare_backends_sorted_by_latency():
    out = mcp_server.compare_backends(corpus_size=100000)
    p50s = [r["p50_ms"] for r in out["server_backends"]]
    assert p50s == sorted(p50s)


def test_compare_backends_rows_carry_verification():
    out = mcp_server.compare_backends(corpus_size=10000)
    for r in out["server_backends"] + out["embedded_backends"]:
        assert {"backend", "recall@10", "p50_ms", "load_s", "index"} <= set(r)
        assert "ann_index_verified" in r


def test_compare_backends_unknown_size_lists_available():
    out = mcp_server.compare_backends(corpus_size=555)
    assert "error" in out
    assert set(out["available"]) == {10000, 100000}


def test_list_traps_filter_by_backend():
    everything = mcp_server.list_traps()
    assert everything["backend_filter"] == "(all)"
    topics = {t["topic"] for t in everything["traps"]}
    assert {"pgvector", "qdrant", "milvus"} <= topics

    qdrant_only = mcp_server.list_traps("qdrant")
    assert qdrant_only["traps"]
    assert all(t["topic"] == "qdrant" for t in qdrant_only["traps"])

    assert mcp_server.list_traps("no-such-backend")["traps"] == []
