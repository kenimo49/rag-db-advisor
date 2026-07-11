# Qdrant

## 実測サマリ (rag-retriever-bench, MIRACL-ja, text-embedding-3-small 1536次元)

- 1万件: 検索 p50 2.0ms / p95 2.3ms、recall@10 0.983（HNSW 勢トップタイ）
- 10万件: 検索 p50 3.3ms、**recall@10 0.947 = HNSW 勢トップ**（厳密検索 0.952 に肉薄）
- 取り込み 1.6秒/1万件・18秒/10万件（gRPC 経由）+ インデックス構築強制 0.5〜1秒
- インデックス: HNSW (m=16, ef_construct=64, hnsw_ef=100)、cosine

## 選定の目安

- 専用ベクトル DB のデファクト候補。HNSW 一本に絞った設計で、パラメータの
  意味がドキュメントと一対一に対応しており迷いが少ない
- ペイロードフィルタ付き検索が主戦場。フィルタ条件と ANN の併用が要件なら最有力
- 単一バイナリ/コンテナで運用が軽い

## 運用の罠（実際に踏んだもの）

### indexing_threshold: green ステータスでも索引されていない

Qdrant はデフォルトで 20MB 未満のセグメントを HNSW 索引化しない
（indexing_threshold）。コレクションのステータスが green でも
`indexed_vectors_count: 0` のまま、全クエリがフルスキャンで返る。
エラーも警告も出ない。数万件規模の検証では
`update_collection(optimizer_config=OptimizersConfigDiff(indexing_threshold=1))`
で構築を強制し、`indexed_vectors_count == points_count` を確認してから測ること。
「小規模だと逆に索引されない」のは直感に反するので注意。

### REST API の 32MB ボディ上限

JSON での一括 upsert は 32MB を超えると 400 で拒否される
（2000点 × 1536次元 ≒ 59MB で即死）。実運用のローダーは gRPC
(`prefer_grpc=True`) を使うこと。速度も REST より上。
