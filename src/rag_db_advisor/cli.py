from __future__ import annotations

import argparse
import json
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="rag-db-advisor",
        description="RAG-stack advisor backed by rag-retriever-bench measurements",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("ingest", help="build the vector store from bundled knowledge")

    ask = sub.add_parser("ask", help="ask a question")
    ask.add_argument("question")
    ask.add_argument("--top-k", type=int, default=6)
    ask.add_argument(
        "--llm",
        action="store_true",
        help="synthesize an answer with OpenAI (default: print evidence only)",
    )
    ask.add_argument("--model", default="gpt-4o-mini")

    sub.add_parser("mcp", help="serve as an MCP server (stdio)")

    args = parser.parse_args()

    if args.command == "ingest":
        from .store import AdvisorStore

        n = AdvisorStore().ingest()
        print(f"ingested {n} chunks")
    elif args.command == "ask":
        if args.llm:
            from .advisor import answer

            result = answer(args.question, top_k=args.top_k, model=args.model)
            print(result["answer"])
            print("\n--- sources ---")
            for c in result["evidence"]:
                print(f"- {c['id']} ({c['source']})")
        else:
            from .advisor import retrieve

            for c in retrieve(args.question, top_k=args.top_k):
                print(f"=== {c['id']} ({c['source']}) ===")
                print(c["text"])
                print()
    elif args.command == "mcp":
        from .mcp_server import main as mcp_main

        mcp_main()
    else:  # pragma: no cover
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
