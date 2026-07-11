"""Knowledge sources: curated notes (markdown) + benchmark results (JSONL).

Every chunk the advisor can retrieve traces back to either a hand-written
operational note or a measured rag-retriever-bench record — no free-floating
claims.
"""

from __future__ import annotations

import json
import re
from importlib import resources
from pathlib import Path
from typing import Any, Iterator

KNOWLEDGE_ROOT = Path(str(resources.files("rag_db_advisor"))) / "knowledge"


def iter_chunks() -> Iterator[dict[str, Any]]:
    yield from _note_chunks()
    yield from _result_chunks()


def _note_chunks() -> Iterator[dict[str, Any]]:
    for path in sorted((KNOWLEDGE_ROOT / "ja").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        title = text.splitlines()[0].lstrip("# ").strip()
        # 「# 見出し」ファイル冒頭 + 「## 節」単位で1チャンク。節は文脈が
        # 自己完結するようファイル見出しを前置する。
        sections = re.split(r"\n(?=## )", text)
        for i, section in enumerate(sections):
            body = section.strip()
            if not body:
                continue
            if i > 0:
                body = f"# {title}\n\n{body}"
            yield {
                "id": f"note:{path.stem}#{i}",
                "text": body,
                "source": f"knowledge/ja/{path.name}",
                "kind": "note",
                "topic": path.stem,
            }


def _result_chunks() -> Iterator[dict[str, Any]]:
    for path in sorted((KNOWLEDGE_ROOT / "results").glob("*.jsonl")):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
            record = json.loads(line)
            if "error" in record:
                continue
            yield {
                "id": f"result:{path.stem}#{line_no}",
                "text": _render_result(record),
                "source": f"rag-retriever-bench results/published/{path.name}",
                "kind": "measurement",
                "topic": record["backend"].get("type", "?"),
            }


def _render_result(r: dict[str, Any]) -> str:
    b = r["backend"]
    q = r["quality"]
    lat = r["latency_ms"]
    build = r["build"]
    k = r["top_k"]
    size = r["corpus_size"]
    check = r.get("self_check", {})
    lines = [
        f"実測: {b['label']} — MIRACL-ja {size:,}件, {r['num_queries']}クエリ, top-{k}",
        f"品質: recall@{k}={q[f'recall@{k}']:.3f}, ndcg@{k}={q[f'ndcg@{k}']:.3f}, "
        f"mrr@{k}={q[f'mrr@{k}']:.3f}",
        f"検索レイテンシ: p50={lat['p50']:.1f}ms, p95={lat['p95']:.1f}ms, p99={lat['p99']:.1f}ms",
        f"書き込み: 取り込み{build['load_seconds']:.1f}秒, インデックス構築{build['index_seconds']:.1f}秒",
        f"構成: server={b.get('server', '?')}, index={b.get('index', '?')}, "
        f"distance={b.get('distance', '?')}"
        + (f", mode={b['mode']}" if b.get("mode") else ""),
    ]
    if check:
        lines.append(
            f"インデックス使用検証: {check.get('ann_index_used')} ({check.get('method', 'n/a')})"
        )
    return "\n".join(lines)


def load_result_tables() -> list[dict[str, Any]]:
    """Raw per-backend records grouped by corpus size, for compare_backends."""
    records = []
    for path in sorted((KNOWLEDGE_ROOT / "results").glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            if "error" not in record:
                records.append(record)
    return records
