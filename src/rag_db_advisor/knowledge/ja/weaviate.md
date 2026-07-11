# Weaviate

## 実測サマリ (rag-retriever-bench, MIRACL-ja, text-embedding-3-small 1536次元)

- 1万件: 検索 p50 1.3ms / p95 1.5ms、recall@10 0.979（HNSW 勢トップタイ）
- 取り込み 3.4秒（挿入時に HNSW 構築込み）、build_index 追加コスト 0
- インデックス: HNSW (max_connections=16, ef_construction=64, ef=100)、cosine

## 選定の目安

- ベクトル+オブジェクトのハイブリッド検索、モジュール機構（re-ranker、
  ベクタライザ内蔵）を使いたいなら候補。BYO ベクトルなら vectorizer none で
- 挿入時にインデックスが積み上がる設計なので、取り込み時間 = 実質の
  インデックス構築時間。ロード後すぐ検索できるのは運用上楽

## 運用の注意（実測から）

### 検索が本当に HNSW かをクエリ単位で確認する手段がない

pgvector の EXPLAIN や ClickHouse の EXPLAIN indexes=1 に相当する
クエリプラン開示がなく、確認できるのはコレクション設定
（vector_index_type: HNSW）まで。設定と実挙動のズレを検出しにくい分、
既知データでの recall 検証を挟むのが安全。

### ポート 8080 は他サービスと衝突しやすい

デフォルトの 8080 は開発機では取り合いになりがち（実測環境では別の
Go サービスが先取りしており、コンテナは healthy なのにホストから 404 が
返る紛らわしい状態になった）。compose でホスト側ポートをずらすのが無難。
gRPC (50051) も同様。

### v4 クライアントは HTTP と gRPC の2ポート必要

接続確認は HTTP だけでなく gRPC 側も。片方だけ通っていると
接続時ヘルスチェックで落ちる。
