# Methodology

How `rag-db-advisor` decides what it's allowed to say. If you're using
the tool, the README is enough. This file exists so that anyone citing
or extending the advisor can inspect the evidence policy directly.

The overriding constraint is simple: **every claim the advisor emits is
grounded in a measurement or a reproduced operational trap, not in
vendor material or model priors.** Everything below follows from that.

## 1. Where the claims come from

Two source classes, and only two:

- **Measurement records** — JSONL rows from `rag-retriever-bench` runs,
  bundled under `src/rag_db_advisor/knowledge/results/`. Each row is
  one backend × one corpus size × one config, produced by the harness
  described in
  [rag-retriever-bench/docs/methodology.md](https://github.com/kenimo49/rag-retriever-bench/blob/main/docs/methodology.md).
  The current cut ships MIRACL-ja at 10k and 100k passages with
  `text-embedding-3-small`.
- **Curated operational notes** — hand-written Markdown under
  `src/rag_db_advisor/knowledge/ja/`, one file per backend plus a
  `cross-cutting.md`. Every trap in these notes was actually hit during
  the bench work and reproduced before being written down. Speculative
  advice is out of scope by policy — if it wasn't measured or hit, it
  doesn't ship.

The retriever pulls chunks from both classes. The MCP `advise` tool
returns the raw chunks; the calling LLM synthesizes the answer over
that evidence. No generation happens inside the server.

## 2. Fail-closed retrieval

A common failure mode for evidence-grounded systems is that when the
retrieval layer errors, the calling LLM silently answers from prior
knowledge and the user never notices. This defeats the whole point.

`rag-db-advisor` surfaces retrieval failures as explicit errors through
a unified MCP error contract across all three tools (`advise`,
`compare_backends`, `list_traps`). An empty result set is also an
error, not a null answer. The calling model sees "no evidence" instead
of "no problem, let me guess."

## 3. Deterministic evidence, no LLM judge

The advisor never runs an LLM to decide which backend is better. It
returns the measurements and the operational notes; the human (or the
calling LLM) does the synthesis.

This matches the bench's own choice — recall / nDCG / MRR / hit@k on
binary qrels, no LLM-as-judge anywhere — and keeps the evidence
reproducible from run to run. If the numbers move, it's because the
bench was re-run, not because a model's refusal rate changed.

## 4. The silent-full-scan class of bug

Three of the seven backends in the underlying bench shipped a way to
degrade silently to full scan or partial-index results. All three were
reproduced during measurement, fixed in the bench, and documented in
this advisor's knowledge base:

- **ClickHouse HNSW** would fall back to brute force if `OPTIMIZE FINAL`
  was skipped after ingest. Search returned correct results, just much
  slower — visible only as a "ClickHouse is slow" impression.
- **Qdrant** ignored a build request when `indexing_threshold_kb` sat
  above the corpus size. Collections came back with
  `indexed_vectors_count = 0` and the "green" status flag stayed on.
- **Milvus** loaded a stale snapshot missing sealed segments after
  flush, so queries returned partial results with no error.

These are documented in `knowledge/ja/clickhouse.md`, `qdrant.md`, and
`milvus.md` respectively, and cross-referenced from
`cross-cutting.md` as the rationale for the general rule *"do not
believe an index is being used without machine-verifying it."*

The reason this matters for a rag-DB **advisor**: a naive advisor that
scrapes vendor docs would tell you the ANN index will be used because
the docs say so. This one tells you the three specific failure modes
where the docs are wrong.

## 5. Numbers you should not extrapolate

The advisor states its regime up front instead of letting numbers travel
unattributed:

- Dataset: MIRACL-ja (Japanese Wikipedia passages, human-annotated qrels).
- Embedding: `text-embedding-3-small` (1536 dim, cosine).
- Corpus sizes: 10k and 100k passages. Anything above that is
  extrapolation and the advisor is required to say so.
- Hardware: single node, localhost network hop for server backends,
  in-process for embedded backends.

Two consequences flow from this:

1. **Embedded vs server latency is not directly comparable.** Chroma and
   LanceDB run in-process and skip the localhost TCP + protobuf hop
   that pgvector / ClickHouse / Qdrant / Weaviate / Milvus all pay. The
   knowledge base and every generated table splits the two classes.
2. **"Measure your own data before deciding" is not a hedge, it's the
   answer.** Recall differences under 3 points and p50 differences
   under a few ms are dominated by dataset shape and query
   distribution. The advisor is a starting point, not a verdict.

## 6. Adding evidence

New evidence is added in exactly one of two ways:

1. **A new bench run.** Drop the JSONL under
   `src/rag_db_advisor/knowledge/results/`. The loader picks it up
   automatically (`knowledge.py::_result_chunks`). Ingest rebuilds the
   store; the new records are addressable by
   `result:<file-stem>#<line-no>` and cite the source file.
2. **A new operational note.** Add a Markdown file under
   `src/rag_db_advisor/knowledge/ja/`. The loader splits it into one
   chunk per H2 section (each carrying the file title for context).
   Only add notes for behavior that was actually reproduced.

The walkthrough with concrete steps lives in
[docs/adding-knowledge.md](adding-knowledge.md).

## 7. Deliberate non-goals

- **The advisor does not benchmark.** Measurement is the bench's job.
  This tool consumes bundled results; it doesn't spin up databases at
  runtime.
- **The advisor does not recommend a single winner.** For most workloads
  in the current corpus range, recall is a statistical tie among HNSW
  backends. The advisor returns the trade-off table and the operational
  notes and lets the caller decide.
- **The advisor does not cover multi-tenant, sharded, or filtered-search
  operating modes** — those are on the bench's own roadmap and will
  arrive here when they arrive there.
- **The advisor does not evaluate embedding models.** Every measurement
  uses the same OpenAI model so backend differences remain isolated.
  For embedding comparisons, use MTEB / JMTEB.

## 8. Citing the advisor

If you use claims from the advisor in a paper, blog post, or vendor
comparison, cite the underlying bench run, not the advisor:

```
rag-retriever-bench, MIRACL-ja, 100k passages,
text-embedding-3-small, HNSW m=16 / ef_c=64 / ef_s=100,
report: results/published/miracl-ja-100000-20260711T053605Z.md
```

The advisor's role is to make the evidence findable. Attribution belongs
to the measurements.
