"""Query any OpenAI-compatible endpoint and write a predictions file for `score.py`.

Works with vLLM, llama-server, TGI, Ollama's OpenAI layer, or a hosted provider: point
``--base-url`` at the endpoint and ``--model`` at the served model name.

    uv run --extra gen python evaluate/run_openai.py \
        --data data/test.jsonl --model Qwen/Qwen3-4B \
        --base-url http://localhost:8000/v1 --out predictions.jsonl

    uv run python evaluate/score.py --data data/test.jsonl --pred predictions.jsonl

The prompt sent to the model is the one stored in each item (`prompt`, system + report), so the
comparison stays apples-to-apples with the published numbers. ``--api-key`` defaults to the
``OPENAI_API_KEY`` environment variable; a local server usually accepts any value.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="data/test.jsonl")
    ap.add_argument("--model", required=True, help="served model name")
    ap.add_argument("--base-url", default="http://localhost:8000/v1")
    ap.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", "unused"))
    ap.add_argument("--out", default="predictions.jsonl")
    ap.add_argument("--limit", type=int, help="only the first N items")
    ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("--temperature", type=float, default=0.0, help="0 = greedy, as published")
    args = ap.parse_args()

    try:
        from openai import OpenAI
    except ImportError:
        sys.exit("needs the openai package: uv run --extra gen python evaluate/run_openai.py ...")

    client = OpenAI(base_url=args.base_url, api_key=args.api_key)
    examples = [json.loads(line) for line in Path(args.data).open(encoding="utf-8") if line.strip()]
    if args.limit:
        examples = examples[: args.limit]

    with Path(args.out).open("w", encoding="utf-8") as out:
        for i, ex in enumerate(examples, 1):
            request = {
                "model": args.model,
                "messages": ex["prompt"],
                "temperature": args.temperature,
                "max_tokens": args.max_tokens,
            }
            # Qwen-style templates think by default; the task wants a direct JSON answer.
            extra = ex.get("chat_template_kwargs")
            if extra:
                request["extra_body"] = {"chat_template_kwargs": extra}
            try:
                response = client.chat.completions.create(**request)
                text = response.choices[0].message.content or ""
            except Exception as exc:  # noqa: BLE001 - record it, keep going
                print(f"[error] {ex['id']}: {exc}", file=sys.stderr)
                text = ""
            out.write(json.dumps({"id": ex["id"], "output": text}, ensure_ascii=False) + "\n")
            if i % 25 == 0:
                print(f"{i}/{len(examples)}", file=sys.stderr)

    print(f"wrote {args.out} ({len(examples)} predictions)", file=sys.stderr)


if __name__ == "__main__":
    main()
