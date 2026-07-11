# 横断知見: RAG 検索バックエンド選定の原則

rag-retriever-bench の実測（MIRACL-ja、日本語 Wikipedia passage、
text-embedding-3-small 1536次元、860 クエリ、qrels 人手正解）から。

## 精度で選ぶな、運用で選べ

同一 HNSW パラメータ (m=16, ef_construction=64, ef_search=100) なら、
pgvector / ClickHouse / Qdrant / Weaviate / Milvus / Chroma の recall@10 は
1万件で 0.979〜0.983 の統計的同着。「どの DB が賢いか」はほぼ無意味な問いで、
差が出るのは (1) レイテンシの固定費構造 (2) 書き込み側の速さ (3) 運用の罠の数、
の3つ。

例外は量子化を既定で挟むもの（LanceDB IVF_HNSW_SQ: 0.89）。
「HNSW と書いてあるか」ではなく「量子化が入るか」を見る。

## 規模の目安

- 〜10万件: brute force（厳密検索）ですら ClickHouse で p50 56ms。
  レイテンシ要件が緩ければインデックスなし=recall 満点という選択肢が残る
- 10万件で HNSW 勢の recall@10 は 0.918〜0.933、厳密検索が 0.952。
  近似のコストは 2〜3.4 ポイント
- コーパスが大きくなると全員 recall が下がる（1万件 0.98 → 10万件 0.93 帯）。
  「うちのデータ・うちの規模」で測らない限り数字は流用できない

## embedded とサーバー型を同じ表で比べない

Chroma / LanceDB (embedded) の p50 にはネットワークホップとサーバー処理が
含まれない。サーバー型と並べると不当に速く見える。比較表では必ず分類を分ける。

## 「インデックスが効いているか」を検証せずに信じない

今回のベンチ構築中、9 バックエンド中 3 つで「エラーなしで劣化する」事象を踏んだ:

1. ClickHouse: 検索時フラグ漏れで HNSW が黙って brute force 化
2. Qdrant: indexing_threshold 未満は green ステータスでも索引ゼロ
3. Milvus: quick-setup が index_params を捨てて AUTOINDEX / ロード可視性で recall 静落ち

共通パターンは「エラーではなく品質かレイテンシの劣化として現れる」こと。
対策: (a) EXPLAIN やサーバー統計でインデックス使用を機械検証する
(b) 既知の正解セットで recall を測ってから本番に流す。
ベンチハーネス側には self_check（プラン/統計検証をレポートに記録）を実装した。

## 書き込み側の性能はしばしば検索より効く

10万件の取り込み+インデックス構築: ClickHouse 18-20秒、pgvector 55秒。
夜間バッチでコーパスを作り直す設計なら、この3倍差は検索 p50 の数 ms 差より
運用に効く。逆に一度作って読むだけなら無視してよい。

## 選定フローの叩き台

1. 既存インフラに PostgreSQL / ClickHouse があるか → あるなら同居を第一候補に
2. 配布するアプリに同梱するか → embedded (Chroma / LanceDB)
3. フィルタ付き検索が主戦場か → Qdrant / Weaviate
4. 数億ベクトルへのスケールパスが確定要件か → Milvus
5. どれでも recall はほぼ同じ。迷ったら運用が一番軽いものを選び、
   自分のデータで recall とレイテンシを測って裏を取る
