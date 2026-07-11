"""MCP server: ask RAG-stack questions from Claude Code / Claude Desktop.

Tools return evidence (measurements + operational notes); the calling LLM
does the synthesis. Only the embedding of the incoming question needs
OPENAI_API_KEY.

Register:
    claude mcp add rag-db-advisor -- rag-db-advisor mcp
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .knowledge import load_result_tables
from .store import AdvisorStore

mcp = FastMCP("rag-db-advisor")
_store: AdvisorStore | None = None


def _get_store() -> AdvisorStore:
    global _store
    if _store is None:
        _store = AdvisorStore()
    return _store


@mcp.tool()
def advise(question: str, top_k: int = 6) -> dict[str, Any]:
    """RAG検索バックエンド選定・チューニングの質問に、実測ベースの根拠を返す。

    返り値の evidence は rag-retriever-bench の実測レコードと運用ノートの
    チャンク。回答はこの evidence の範囲で合成し、数値には source を添えること。
    失敗時は {"error": ..., "hint": ...} を返す (例外は投げない)。
    """
    try:
        evidence = _get_store().retrieve(question, top_k)
    except RuntimeError as exc:
        return {"error": str(exc), "hint": "run `rag-db-advisor ingest` first"}
    return {
        "question": question,
        "evidence": evidence,
        "note": (
            "実測は MIRACL-ja / text-embedding-3-small / 単一ノード Docker での結果。"
            "evidence にない数値は引用しないこと。"
        ),
    }


@mcp.tool()
def compare_backends(corpus_size: int = 100000) -> dict[str, Any]:
    """指定コーパス規模の全バックエンド実測値を比較表として返す。

    corpus_size は 10000 か 100000。品質 (recall/ndcg/mrr@10)、レイテンシ
    (p50/p95)、書き込み時間、インデックス使用検証の結果を含む。
    """
    rows = []
    for r in load_result_tables():
        if r["corpus_size"] != corpus_size:
            continue
        b, q, lat, build = r["backend"], r["quality"], r["latency_ms"], r["build"]
        rows.append(
            {
                "backend": b["label"],
                "mode": b.get("mode", "server"),
                "recall@10": round(q["recall@10"], 3),
                "ndcg@10": round(q["ndcg@10"], 3),
                "p50_ms": round(lat["p50"], 1),
                "p95_ms": round(lat["p95"], 1),
                "load_s": round(build["load_seconds"], 1),
                "index_s": round(build["index_seconds"], 1),
                "index": b.get("index", "?"),
                "ann_index_verified": r.get("self_check", {}).get("ann_index_used"),
            }
        )
    if not rows:
        sizes = sorted({r["corpus_size"] for r in load_result_tables()})
        return {"error": f"no measurements at corpus_size={corpus_size}", "available": sizes}
    server = [r for r in rows if "embedded" not in str(r["mode"])]
    embedded = [r for r in rows if "embedded" in str(r["mode"])]
    return {
        "corpus_size": corpus_size,
        "dataset": "MIRACL-ja (860 queries, human qrels), text-embedding-3-small",
        # 別配列で返す: embedded は in-process でネットワークホップがなく、
        # server 型と同列のレイテンシランキングにしてはいけない
        "server_backends": sorted(server, key=lambda r: r["p50_ms"]),
        "embedded_backends": sorted(embedded, key=lambda r: r["p50_ms"]),
        "caveat": "embedded (in-process) はネットワークホップがなく、server 型とレイテンシ直接比較不可",
    }


@mcp.tool()
def list_traps(backend: str = "") -> dict[str, Any]:
    """実際に踏んだ運用の罠一覧を返す。

    backend 指定で絞り込み (pgvector/clickhouse/qdrant/weaviate/milvus/chroma/lancedb)。
    """
    from .knowledge import iter_chunks

    # 運用ノートは「## 運用の罠」「## 運用の注意」節が1チャンクになっている
    traps = [
        {"topic": c["topic"], "source": c["source"], "text": c["text"]}
        for c in iter_chunks()
        if c["kind"] == "note"
        and "## 運用の" in c["text"]
        and (not backend or c["topic"] == backend)
    ]
    return {"backend_filter": backend or "(all)", "traps": traps}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
