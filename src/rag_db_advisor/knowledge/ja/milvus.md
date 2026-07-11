# Milvus

## 実測サマリ (rag-retriever-bench, MIRACL-ja, text-embedding-3-small 1536次元)

- 1万件: 検索 p50 1.6ms / p95 1.8ms、recall@10 0.980（修正後。下記の罠を参照）
- 取り込み 0.8秒 + flush/インデックス構築/ロード 6.7秒
- インデックス: HNSW (M=16, efConstruction=64, ef=100)、cosine
- standalone は単一コンテナ（embedded etcd + local storage）で立つが、
  アーキテクチャ上は分散前提の最重量級

## 選定の目安

- 数億ベクトル級へのスケールパスが最初から要件にあるなら候補
- 10万件規模では他の HNSW 勢と品質・速度とも差がない。運用の重さ
  （コンポーネント数、ロード状態の管理）を引き受ける理由が要る
- GPU インデックスなど大規模向け機能が必要になったときの引っ越し先

## 運用の罠（実際に踏んだもの）

### quick-setup が index_params を黙って捨てる

`MilvusClient.create_collection(name, dimension=...)` の簡易パスに
index_params を渡しても無視され、AUTOINDEX が作られる。HNSW を指定した
つもりが別物になっていた（describe_index で index_type: AUTOINDEX と判明）。
HNSW パラメータを制御したいなら明示 schema + prepare_index_params 経由で
作ること。作った後は describe_index で index_type を必ず確認。

### ロード可視性: 検索がセグメントの一部しか見ない

コレクションは作成時に自動ロードされるが、そのスナップショットは
flush 後に sealed されたセグメントを含まない。search はエラーなしで
「見えている分だけ」から top-k を返すため、recall だけが静かに下がる
（実測: 同一インデックスで 0.922 → release+load 後 0.980）。
refresh_load も Loaded を返しながら裏でロード中のことがある。
確実なのは release_collection → load_collection → get_load_state が
Loaded になるまで待つ、の全再ロード。
「エラーではなく品質劣化として現れる」ため、ベンチマークや本番導入時は
既知クエリで recall を検証してから流すこと。
