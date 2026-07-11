# Chroma

## 実測サマリ (rag-retriever-bench, MIRACL-ja, text-embedding-3-small 1536次元)

- 1万件 (embedded/in-process): 検索 p50 1.3ms / p95 1.5ms、recall@10 0.980
- 取り込み 1.9秒、build_index 追加コスト 0（挿入時に構築）
- インデックス: HNSW (M=16, construction_ef=64, search_ef=100)、cosine
- 注意: embedded はネットワークホップがないため、サーバー型の p50 と
  直接比較してはいけない（別クラスとして読むこと）

## 選定の目安

- プロトタイピングと数十万件までの組み込み用途の定番。pip install だけで
  永続化込みの HNSW が動く
- RAG アプリに同梱して配る（ユーザーにサーバーを立てさせない）用途に最適。
  数百〜数万チャンクの知識ベースならこれで足りることが多い
- サーバーモードもあるが、embedded で始めて必要になったら移行が現実的

## 運用の注意（実測から）

### プラン introspection がない

インデックス使用をクエリ単位で確認する手段がなく、確認できるのは
コレクション metadata の hnsw:* 設定値まで。設定ミス（space の指定漏れで
デフォルト l2 のまま、など）は数値検証でしか捕まえられない。
cosine を使うなら `hnsw:space: cosine` を明示すること。

### add() のバッチ上限

一括 add はおよそ 5,461 件で上限に当たる。チャンク分割して投入する。
