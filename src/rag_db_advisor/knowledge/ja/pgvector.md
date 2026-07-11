# pgvector (PostgreSQL)

## 実測サマリ (rag-retriever-bench, MIRACL-ja, text-embedding-3-small 1536次元)

- 10万件: 検索 p50 4.8ms / p95 6.1ms、recall@10 0.936。専用ベクトルDB勢 (1.8〜3.3ms) に次ぐ位置
- 1万件: p50 1.9ms、recall@10 0.980
- 書き込みは最遅クラス: 10万件で COPY 取り込み 32秒 + HNSW インデックス構築 24秒 = 約56秒（ClickHouse は合計 19-20秒）
- インデックス: HNSW (m=16, ef_construction=64, ef_search=100)、cosine

## 選定の目安

- 既に PostgreSQL を運用しているなら第一候補。トランザクション・JOIN・row-level security と同居できる
- 数万件規模までは検索レイテンシ最速級。10万件では専用ベクトルDB勢が上に来るが、p50 4.8ms は大半の RAG で十分速い。コーパスを頻繁に作り直す用途ではインデックス構築の遅さが効いてくる
- EXPLAIN でインデックス使用を確認できる（クエリプランの透明性が高い）

## 運用の罠（実際に踏んだもの）

### 並列 HNSW ビルドの共有メモリ要求

`maintenance_work_mem = 2GB` + `max_parallel_maintenance_workers` で並列ビルドすると、
約 2.1GB の動的共有メモリセグメントを要求する。Docker コンテナの `/dev/shm`
（compose デフォルト 64MB、明示しても 1GB 程度にしがち）を超えると:

```
psycopg.errors.DiskFull: could not resize shared memory segment
"/PostgreSQL.xxx" to 2144407008 bytes: No space left on device
```

1万件では顕在化せず、10万件で初めて出る。対策は compose の `shm_size: 4g`。
「DiskFull」という名前だがディスクではなく共有メモリの問題。

### ef_search はセッション設定

`SET hnsw.ef_search = 100` はセッション単位。コネクションプール経由では
クエリごとに設定されているか確認が必要。
