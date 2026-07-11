"""Answer synthesis on top of the store.

MCP mode returns raw evidence and lets the calling LLM (Claude etc.)
synthesize — no generation key needed server-side. CLI mode can optionally
synthesize with OpenAI when --llm is passed.
"""

from __future__ import annotations

from typing import Any

from .store import AdvisorStore

SYSTEM_PROMPT = """あなたは RAG の検索バックエンド選定を助けるアドバイザーです。
以下のルールを厳守してください。
- 回答は与えられた evidence の範囲でのみ行う。evidence にない数値・事実を作らない
- 数値を引くときは必ず出典 (source) を添える
- evidence が質問に答えるのに不十分なら、その旨を明言する
- 実測は MIRACL-ja (日本語 Wikipedia) / text-embedding-3-small での結果であり、
  別のデータ・埋め込みでは変わりうることを必要に応じて注意する
- 日本語で簡潔に答える"""


def retrieve(question: str, top_k: int = 6, store: AdvisorStore | None = None) -> list[dict[str, Any]]:
    return (store or AdvisorStore()).retrieve(question, top_k)


def answer(question: str, top_k: int = 6, model: str = "gpt-4o-mini") -> dict[str, Any]:
    store = AdvisorStore()
    evidence = store.retrieve(question, top_k)
    from openai import OpenAI

    blocks = "\n\n---\n\n".join(
        f"[source: {c['source']}]\n{c['text']}" for c in evidence
    )
    res = OpenAI().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"## Evidence\n\n{blocks}\n\n## 質問\n\n{question}"},
        ],
    )
    return {
        "answer": res.choices[0].message.content,
        "evidence": evidence,
        "model": model,
    }
