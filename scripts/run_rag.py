from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}: sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.rag_pipeline import run_rag

def main() -> int:
    parser = argparse.ArgumentParser(description="Run local ValueSignal SEC filing RAG")
    parser.add_argument("query"); parser.add_argument("--ticker"); parser.add_argument("--form")
    parser.add_argument("--mode", choices=("bm25", "embedding", "hybrid"), default="hybrid")
    parser.add_argument("--top-k", type=int, default=3); parser.add_argument("--no-synthesize", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run_rag(args.query, args.ticker, args.form, args.mode, args.top_k, not args.no_synthesize), indent=2))
    return 0

if __name__ == "__main__": raise SystemExit(main())
