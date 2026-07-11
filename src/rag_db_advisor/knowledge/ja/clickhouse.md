# ClickHouse

## 実測サマリ (rag-retriever-bench, MIRACL-ja, text-embedding-3-small 1536次元)

- 10万件 HNSW (index_granularity=8192 デフォルト): 検索 p50 43.1ms、recall@10 0.923
- 10万件 HNSW (index_granularity=128 チューニング後): **p50 11.5ms**、recall@10 0.921。スケールしてもほぼ横ばい（1万件 9.0ms → 10万件 11.5ms）
- 10万件 brute force（インデックスなし）: p50 65.9ms、recall@10 0.952（厳密検索 = 品質の天井）
- 書き込みは速い: 10万件で取り込み 11-13秒 + OPTIMIZE FINAL 8秒
- vector_similarity インデックスは 25.x 時点で experimental

## 選定の目安

- 既に ClickHouse で分析基盤を持っているなら、ベクトル検索を同居させる選択肢として現実的
- 10万件規模なら brute force ですら p50 66ms — 「インデックスなしで厳密検索」が許される規模は意外と広い
- 大量データの取り込み・作り直しが多いパイプラインでは書き込み側の速さが効く

## 列指向×ベクトル検索の本質: granule 読み増幅

HNSW インデックスが返すのは「候補 granule」であり、再スコアリングで
embedding 列を granule 丸ごと読む。granule が大きい（デフォルト 8192行）と
top-10 のヒットが散らばって読み出しが増幅する。

- index_granularity 8192 → 128 で p50 43.1ms → 11.5ms（3.7倍）
- 再スコアリング対象行数は 10 granule × 8192行 ≒ 82,000行 → 1,280行 に激減する
- recall への影響は小さくラン間ノイズと同程度（ラン間で −0.002〜−0.008、g=128 側が
  わずかに低い傾向）。効果はほぼレイテンシ側に出る

## 運用の罠（実際に踏んだもの）

### 検索時フラグがないとインデックスが黙って無視される

`allow_experimental_vector_similarity_index = 1` は **クエリ実行時にも** 必要。
テーブル作成時だけ設定して検索時に付け忘れると、エラーなしで brute force に
なる（HNSW のつもりが 27ms、brute force が 31ms で「ほぼ同じ」になり発覚）。
EXPLAIN indexes=1 でスキップインデックスの使用を確認すること。

### 挿入時インデックス構築のタイムアウト

index_granularity を小さくしたテーブルへの大量 INSERT は、挿入時スキップ
インデックス構築が遅くなり、サーバーの http_receive_timeout (30秒) を突いて
SOCKET_TIMEOUT で死ぬことがある。`materialize_skip_indexes_on_insert = 0` で
構築を OPTIMIZE FINAL に遅延させると、取り込みは純粋な取り込みになる。
