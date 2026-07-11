# Adding knowledge

How to add a new backend, a new bench run, or a new operational trap to
the advisor. Companion to [docs/methodology.md](methodology.md), which
explains *why* the evidence policy is shaped this way.

The advisor's knowledge lives entirely under
`src/rag_db_advisor/knowledge/` and is bundled into the wheel via
`tool.setuptools.package-data`. The loader in `knowledge.py` reads it
through `importlib.resources` so it works from editable installs, wheels,
and zipped installs alike.

Two classes of chunk:

- **Notes** — hand-written Markdown, `knowledge/ja/*.md`
- **Measurements** — JSONL from `rag-retriever-bench`, `knowledge/results/*.jsonl`

Both are indexed together by `rag-db-advisor ingest`. The MCP / CLI
retrieval then returns whichever chunks best match the question,
regardless of class.

## Adding a new operational note

Notes are how reproduced traps and hand-earned selection rules enter the
advisor. If a claim isn't a bench measurement, it needs to be here.

### 1. Pick or create the file

- Per-backend content goes in `knowledge/ja/<backend>.md`.
- Cross-cutting content (comparisons, rules-of-thumb across backends)
  goes in `knowledge/ja/cross-cutting.md`.

Existing files are the template. Structure:

```markdown
# <backend name> (<engine class>)

## 実測サマリ (rag-retriever-bench, MIRACL-ja, ...)

- One line per measured behavior worth carrying forward, with the
  source scale (10k / 100k).

## 選定の目安

Two to five bullet points on when this backend is the right choice
and when it isn't. Each bullet should be derivable from the measured
summary above or from the traps below.

## 運用の罠（実際に踏んだもの）

### <specific trap name>

Reproduction context, the failure signature, and the fix. Only
include traps that were actually reproduced during measurement.
```

### 2. Understand how the loader will chunk it

`knowledge.py::_note_chunks` splits each file on `## ` boundaries. Every
H2 section becomes one chunk, and the file title (`# ...`) is prepended
to every section past the first so each chunk stands alone when
retrieved out of context.

Consequences:

- **Keep sections self-contained.** A user question can retrieve section
  3 without seeing sections 1 or 2.
- **Don't rely on cross-section pronouns** ("as noted above", "the same
  fix applies"). The retriever won't respect that.
- **One trap per H3 under a shared H2** is fine — H3s stay inside their
  parent chunk. Use this when three related traps share a rationale.

### 3. Rebuild the store

```bash
rag-db-advisor ingest
```

Ingest always drops and recreates the Chroma collection and the
`chunks.json` manifest, so rebuilds are idempotent — no separate
"clean" step is needed. The manifest is invalidated *before* the
rebuild starts, so an interrupted ingest reads as "broken" rather than
serving the previous generation.

### 4. Test the retrieval

```bash
rag-db-advisor ask "<question that should hit the new note>"
```

Confirm the new chunk appears in the top-k results with the expected
source path (`knowledge/ja/<file>.md`). If it doesn't, the section
wording is too far from likely question phrasing — rewrite to include
the terms a user would actually type.

## Adding a new bench run

When rag-retriever-bench emits a new results JSONL you want the advisor
to know about:

### 1. Drop the file in

```bash
cp path/to/rag-retriever-bench/results/published/miracl-ja-XXX.jsonl \
   src/rag_db_advisor/knowledge/results/
```

File naming convention: `<dataset>-<corpus-size>-<timestamp>.jsonl`. The
loader uses the file stem as the citation, so the name is user-visible
in every retrieved chunk.

### 2. Confirm the loader will accept it

`knowledge.py::_result_chunks` expects each JSONL line to be one record
with the shape rag-retriever-bench emits: `backend`, `quality`,
`latency_ms`, `build`, `top_k`, `corpus_size`, `num_queries`, and an
optional `self_check`. Lines with an `error` field are skipped, which
is how partially-failed runs are safely bundled.

`_render_result` turns each record into the natural-language chunk that
gets embedded. If you add fields you want retrievable, add them there
and re-ingest.

### 3. Update the changelog

Bench runs are user-visible evidence changes. Add an entry to
`CHANGELOG.md` under `## [Unreleased]` describing which run was added
and what corpus size / dataset it covers.

### 4. Rebuild + smoke test

```bash
rag-db-advisor ingest
rag-db-advisor ask "compare backends at <new corpus size>"
```

## Adding a new backend

A new backend to the advisor's knowledge base is *not* the same as
adding one to `rag-retriever-bench`. Sequence:

1. **Add it to the bench first.** See
   [rag-retriever-bench/docs/adding-a-backend.md](https://github.com/kenimo49/rag-retriever-bench/blob/main/docs/adding-a-backend.md).
   Get a full run out with a working `self_check`.
2. **Add the results JSONL here** (steps under "Adding a new bench
   run"). The advisor immediately gains quantitative facts about the
   backend.
3. **Add the operational note here** (steps under "Adding a new
   operational note"), file name matching the backend key
   (`knowledge/ja/<backend>.md`). This is where selection rules and
   trap catalog live.
4. **Update `cross-cutting.md`** if the new backend changes any
   cross-backend rule (e.g. shifts a "not quality-tied" claim).
5. **Update `CHANGELOG.md`** — new backends are user-visible.

Do not add a note file for a backend that has no measurements yet. The
advisor's contract is that every backend it discusses has been
measured; a note-only backend would violate the evidence policy.

## Testing after any change

The test suite guards against contract regressions:

```bash
pytest -q
```

Relevant modules: `tests/test_knowledge.py` checks the loader,
`tests/test_store.py` covers ingestion, `tests/test_mcp_server.py`
exercises the tool surface, `tests/test_cli.py` covers the CLI paths.
If you add a new chunk kind or change `_render_result`, expect to
extend these.
