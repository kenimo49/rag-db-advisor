"""Chunking invariants: every chunk traceable, self-contained, unique."""

from rag_db_advisor import knowledge


def test_chunks_have_required_fields():
    chunks = list(knowledge.iter_chunks())
    assert chunks
    for c in chunks:
        assert c["id"]
        assert c["text"].strip()
        assert c["source"]
        assert c["kind"] in {"note", "measurement"}
        assert c["topic"]


def test_both_kinds_present():
    kinds = {c["kind"] for c in knowledge.iter_chunks()}
    assert kinds == {"note", "measurement"}


def test_ids_unique():
    ids = [c["id"] for c in knowledge.iter_chunks()]
    assert len(ids) == len(set(ids))


def test_note_sections_carry_file_title():
    # A "## section" chunk must be self-contained: the file's "# title" is
    # prepended so the retriever never returns a context-free fragment.
    notes = [c for c in knowledge.iter_chunks() if c["kind"] == "note"]
    sections = [c for c in notes if not c["id"].endswith("#0")]
    assert sections
    for c in sections:
        assert c["text"].startswith("# "), c["id"]


def test_measurement_chunks_cite_bench_results():
    measurements = [c for c in knowledge.iter_chunks() if c["kind"] == "measurement"]
    assert measurements
    for c in measurements:
        assert "rag-retriever-bench" in c["source"]
        assert "実測:" in c["text"]


def test_render_result_formats_ja_facts():
    record = {
        "backend": {
            "label": "qdrant",
            "type": "qdrant",
            "server": "Qdrant 1.18.2",
            "index": "hnsw(m=16)",
            "distance": "cosine",
        },
        "num_queries": 860,
        "top_k": 10,
        "corpus_size": 100000,
        "quality": {"recall@10": 0.947, "ndcg@10": 0.9, "mrr@10": 0.88},
        "latency_ms": {"p50": 3.3, "p95": 5.0, "p99": 8.1},
        "build": {"load_seconds": 18.0, "index_seconds": 1.0},
        "self_check": {"ann_index_used": True, "method": "server stats"},
    }
    text = knowledge._render_result(record)
    assert "MIRACL-ja 100,000件" in text
    assert "recall@10=0.947" in text
    assert "p50=3.3ms" in text
    assert "インデックス使用検証: True (server stats)" in text


def test_load_result_tables_skips_error_records():
    for record in knowledge.load_result_tables():
        assert "error" not in record
        assert "quality" in record
