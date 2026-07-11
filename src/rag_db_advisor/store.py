"""Vector store wiring — dogfoods rag-retriever-bench's retriever abstraction.

The advisor's own corpus is a few hundred chunks. The benchmark data says
that at this scale every HNSW backend is quality-tied (recall@10 0.979-0.983
at 10k docs), so the pick is operational: Chroma embedded needs no server and
ships with `pip install`. Exactly the advice the advisor gives — applied to
itself. Swap via RRB-style options if you want a server backend.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np
from openai import OpenAI
from rag_retriever_bench.retrievers import create_retriever

from .knowledge import iter_chunks

EMBED_MODEL = "text-embedding-3-small"
EMBED_DIM = 1536


def default_home() -> Path:
    return Path(os.environ.get("RAG_DB_ADVISOR_HOME", Path.home() / ".rag-db-advisor"))


class AdvisorStore:
    def __init__(self, home: Path | None = None, backend_options: dict[str, Any] | None = None):
        self.home = home or default_home()
        self.home.mkdir(parents=True, exist_ok=True)
        self.chunks_path = self.home / "chunks.json"
        self.retriever = create_retriever(
            backend_options
            or {
                "type": "chroma",
                "label": "advisor-store",
                "path": str(self.home / "chroma"),
                "hnsw": {"m": 16, "ef_construction": 64, "ef_search": 100},
            }
        )
        self._chunks: dict[str, dict[str, Any]] | None = None
        self._openai: OpenAI | None = None

    # ---- ingest -----------------------------------------------------------
    def ingest(self) -> int:
        chunks = list(iter_chunks())
        texts = [c["text"] for c in chunks]
        ids = [c["id"] for c in chunks]
        vecs = self._embed(texts)
        self.retriever.setup(dim=EMBED_DIM)
        self.retriever.load(ids, texts, vecs)
        self.retriever.build_index()
        self.chunks_path.write_text(
            json.dumps({c["id"]: c for c in chunks}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        return len(chunks)

    # ---- query ------------------------------------------------------------
    def retrieve(self, question: str, top_k: int = 6) -> list[dict[str, Any]]:
        if not self.chunks_path.exists():
            raise RuntimeError("store is empty — run `rag-db-advisor ingest` first")
        if self._chunks is None:
            self._chunks = json.loads(self.chunks_path.read_text(encoding="utf-8"))
        qvec = self._embed([question])[0]
        ids = self.retriever.search(qvec, top_k)
        return [self._chunks[i] for i in ids if i in self._chunks]

    # ---- embeddings -------------------------------------------------------
    def _embed(self, texts: list[str]) -> np.ndarray:
        if self._openai is None:
            self._openai = OpenAI()
        out: list[list[float]] = []
        batch = 128
        for i in range(0, len(texts), batch):
            res = self._openai.embeddings.create(
                model=EMBED_MODEL, input=texts[i : i + batch]
            )
            out.extend(d.embedding for d in res.data)
        return np.asarray(out, dtype=np.float32)
