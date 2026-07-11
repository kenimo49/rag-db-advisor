# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — 2026-07-11

Initial release. Evidence-based advisor for RAG stack decisions, wrapping
the [rag-retriever-bench](https://github.com/kenimo49/rag-retriever-bench)
measurements as a Chroma-backed knowledge store and serving them over MCP
and CLI. Every claim the advisor emits is anchored to a bundled
measurement or a reproduced operational trap.

### Added

- Knowledge base built from rag-retriever-bench v0.1.0 output:
  - Per-backend design notes (pgvector, ClickHouse, Qdrant, Weaviate,
    Milvus, Chroma, LanceDB) with measured recall / latency at 10k and
    100k MIRACL-ja scale.
  - Cross-cutting selection guide covering the "same-recall / different
    operations" rule, embedded-vs-server comparison hygiene, and
    write-side cost.
  - Reproduced operational traps: silent HNSW-to-full-scan degradation
    on ClickHouse / Qdrant / Milvus, pgvector planner ignoring HNSW
    below ~4k rows, pgvector `shm_size` requirement at 100k scale,
    Milvus load visibility.
- MCP server (`rag-db-advisor mcp`) exposing three tools:
  - `advise(question, top_k)` — retrieve measured evidence for a
    free-form question; the calling LLM synthesizes the answer.
  - `compare_backends(corpus_size)` — full comparison table at 10k /
    100k passages (quality, latency, build time, index verification
    method).
  - `list_traps(backend)` — operational traps actually hit during
    measurement, filterable by backend.
- CLI (`rag-db-advisor ask`) with `--llm` for optional OpenAI synthesis
  and evidence-only default mode.
- Ingest command (`rag-db-advisor ingest`) that builds the local
  knowledge store from bundled `knowledge/**/*` resources — no external
  service required beyond the OpenAI embedding call.
- Dogfooded retrieval layer: imports `rag-retriever-bench`'s
  `BaseRetriever` abstraction and picks Chroma (embedded) because the
  bench data shows every HNSW backend is quality-tied at this KB size,
  so operational lightness wins.
- Zip-safe resource loading via `importlib.resources` so the bundled
  knowledge / results ship correctly from installed wheels and
  editable installs alike.
- Fail-closed retrieval: retrieval failures surface as explicit errors
  rather than empty results, so the calling LLM cannot silently answer
  from prior knowledge.
- Unified MCP error contract across all three tools.
- Test suite covering CLI, MCP server, knowledge loader, and store,
  plus GitHub Actions CI (ruff + pytest on Python 3.10 and 3.12).
- `rag-retriever-bench` dependency pinned to `v0.1.0` so a breaking
  change on the bench's `main` cannot break installs here.

[Unreleased]: https://github.com/kenimo49/rag-db-advisor/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/kenimo49/rag-db-advisor/releases/tag/v0.1.0
