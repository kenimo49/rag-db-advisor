"""CLI dispatch smoke tests — store and synthesis faked."""

import pytest

from rag_db_advisor import cli


def test_ingest_command(monkeypatch, capsys):
    class FakeStore:
        def ingest(self):
            return 54

    monkeypatch.setattr("rag_db_advisor.store.AdvisorStore", FakeStore)
    monkeypatch.setattr("sys.argv", ["rag-db-advisor", "ingest"])
    cli.main()
    assert "ingested 54 chunks" in capsys.readouterr().out


def test_ask_prints_evidence_with_sources(monkeypatch, capsys):
    chunk = {"id": "note:qdrant#2", "text": "indexing_threshold の罠", "source": "knowledge/ja/qdrant.md"}
    monkeypatch.setattr("rag_db_advisor.advisor.retrieve", lambda q, top_k: [chunk])
    monkeypatch.setattr("sys.argv", ["rag-db-advisor", "ask", "小規模で索引されない?"])
    cli.main()
    out = capsys.readouterr().out
    assert "note:qdrant#2" in out
    assert "knowledge/ja/qdrant.md" in out
    assert "indexing_threshold" in out


def test_ask_requires_question(monkeypatch):
    monkeypatch.setattr("sys.argv", ["rag-db-advisor", "ask"])
    with pytest.raises(SystemExit):
        cli.main()
