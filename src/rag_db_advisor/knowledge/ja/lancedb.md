# LanceDB

## 実測サマリ (rag-retriever-bench, MIRACL-ja, text-embedding-3-small 1536次元)

- 1万件 (embedded/file-backed): 検索 p50 1.7ms / p95 2.0ms、**recall@10 0.892**
- 取り込み 0.1秒（Arrow テーブル直書き、圧倒的最速）+ インデックス構築 0.4秒
- インデックス: IVF_HNSW_SQ — IVF パーティション上の HNSW + 8bit スカラー量子化。
  他バックエンドの「素の HNSW」とはパラメータ同一でも別物

## 選定の目安

- サーバーレス（ファイルベース）でオブジェクトストレージに直接置ける設計。
  Lakehouse 構成・バッチ分析と相性が良い
- 取り込みが桁違いに速い。Arrow/Parquet エコシステムに乗っているなら候補
- recall 要件が厳しい用途では量子化の代償を測ってから

## 運用の注意（実測から）

### SQ 量子化の recall 代償は約9ポイント

同一データ・同一 embedding で素の HNSW 勢が recall@10 0.98 のところ、
IVF_HNSW_SQ は 0.89。8bit スカラー量子化で距離計算が近似になるため。
`refine_factor` を指定すると全精度ベクトルで再ランキングして回復できる
（読み出しが増えるトレードオフ）。「HNSW って書いてあるから同じ」ではない。

### インデックス API が世代交代中

create_index の metric/num_partitions 引数スタイルは deprecated。
バージョン更新で書き方が変わりやすいので、ピン留めと release note 確認を。

### 検証手段は list_indices まで

クエリプランの開示はなく、インデックスの存在と統計
（num_indexed_rows / num_unindexed_rows）で確認する。
