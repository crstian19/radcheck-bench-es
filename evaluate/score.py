"""Score model predictions on RadCheck-Bench-ES without depending on the radcheck package.

The matching rule is the one used to build the published numbers:

* the predicted ``tipo`` must equal the gold ``tipo``;
* the predicted ``fragmento`` is located in the report (exact match first, then a
  case-insensitive match that tolerates whitespace differences) and must overlap the gold
  span **or its counterpart** -- from the text alone either side of a contradiction may be
  the wrong one;
* if the fragment cannot be located at all, the prediction still counts when it *contains*
  the changed text, which keeps credit for answers that quote the edit loosely.

A prediction is a false positive when it matches no gold error. A gold error with no
matching prediction is a false negative. Invalid JSON counts as "no prediction".

Usage::

    uv run python evaluate/score.py --data data/test.jsonl --pred predictions.jsonl
    uv run python evaluate/score.py --data data/test.jsonl --pred preds.jsonl --out scores.json

Prediction file format, one JSON object per line (``output`` is the raw model text)::

    {"id": "rcb-0001", "output": "{\\"errores\\": [...]}"}
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

# The three scored contradiction types, plus the two out-of-scope ones that can show up in
# the extra track or in a model's answer.
ERROR_TYPES = ("lateralidad", "negacion", "medida")
EXTENDED_TYPES = ("discordancia", "transcripcion")
ALL_ERROR_TYPES = ERROR_TYPES + EXTENDED_TYPES

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def parse_output(text: str) -> list[dict] | None:
    """Extract the error list from a model answer. ``None`` if no valid JSON object found.

    Mirrors radcheck's parser: thinking blocks are stripped and the first JSON object that
    carries an ``"errores"`` list wins, so prose around the JSON is tolerated.
    """
    if not isinstance(text, str):
        return None
    text = _THINK_RE.sub("", text)
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text, i)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("errores"), list):
            return [e for e in obj["errores"] if isinstance(e, dict)]
    return None


def locate(fragment: str, report: str) -> tuple[int, int] | None:
    """Find a predicted fragment in the report, tolerating case and whitespace changes."""
    if not fragment:
        return None
    i = report.find(fragment)
    if i != -1:
        return i, i + len(fragment)
    pattern = r"\s+".join(re.escape(tok) for tok in fragment.split())
    m = re.search(pattern, report, re.IGNORECASE)
    return (m.start(), m.end()) if m else None


def matches(pred: dict, gold: dict, report: str) -> bool:
    """True when a predicted error matches one gold error."""
    if pred.get("tipo") != gold.get("tipo"):
        return False
    span = locate(str(pred.get("fragmento", "")), report)
    if span is not None:
        targets = [(gold["start"], gold["end"])]
        if gold.get("counterpart"):
            targets.append(tuple(gold["counterpart"]))
        return any(span[0] < end and start < span[1] for start, end in targets)
    # Fragment not found verbatim: accept it if it at least contains the changed text.
    changed = report[gold["start"] : gold["end"]].lower()
    return bool(changed) and changed in str(pred.get("fragmento", "")).lower()


@dataclass
class Scores:
    tp: Counter = field(default_factory=Counter)
    fp: Counter = field(default_factory=Counter)
    fn: Counter = field(default_factory=Counter)
    examples: int = 0
    invalid_json: int = 0
    clean: int = 0
    clean_flagged: int = 0
    corrupted: int = 0
    corrupted_flagged: int = 0

    def add(self, report: str, gold: list[dict], pred: list[dict] | None) -> None:
        self.examples += 1
        if pred is None:
            self.invalid_json += 1
            pred = []
        if gold:
            self.corrupted += 1
            self.corrupted_flagged += bool(pred)
        else:
            self.clean += 1
            self.clean_flagged += bool(pred)
        unmatched = list(gold)
        for p in pred:
            hit = next((g for g in unmatched if matches(p, g, report)), None)
            tipo = p.get("tipo") if p.get("tipo") in ALL_ERROR_TYPES else "otro"
            if hit is None:
                self.fp[tipo] += 1
            else:
                unmatched.remove(hit)
                self.tp[tipo] += 1
        for g in unmatched:
            self.fn[g["tipo"]] += 1

    def summary(self) -> dict:
        def prf(tp: int, fp: int, fn: int) -> dict:
            p = tp / (tp + fp) if tp + fp else 0.0
            r = tp / (tp + fn) if tp + fn else 0.0
            f1 = 2 * p * r / (p + r) if p + r else 0.0
            return {
                "precision": round(p, 3),
                "recall": round(r, 3),
                "f1": round(f1, 3),
                "support": tp + fn,
            }

        # Extended types only appear when the data or the model uses them.
        seen = set(self.tp) | set(self.fp) | set(self.fn)
        types = ERROR_TYPES + tuple(t for t in EXTENDED_TYPES if t in seen)
        per_type = {t: prf(self.tp[t], self.fp[t], self.fn[t]) for t in types}
        overall = prf(sum(self.tp.values()), sum(self.fp.values()), sum(self.fn.values()))
        return {
            "examples": self.examples,
            "overall": overall,
            "per_type": per_type,
            "false_alarm_rate": round(self.clean_flagged / self.clean, 3) if self.clean else None,
            "detection_rate": round(self.corrupted_flagged / self.corrupted, 3)
            if self.corrupted
            else None,
            "invalid_json_rate": round(self.invalid_json / self.examples, 3)
            if self.examples
            else None,
        }


def load_jsonl(path: str | Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def score(data: list[dict], predictions: dict[str, str]) -> dict:
    """Score a ``{id: raw model text}`` mapping against evaluation-format examples."""
    scores = Scores()
    missing: list[str] = []
    for ex in data:
        raw = predictions.get(ex["id"])
        if raw is None:
            missing.append(ex["id"])
        scores.add(ex["prompt"][1]["content"], ex["gold"], parse_output(raw or ""))
    summary = scores.summary()
    if missing:
        summary["missing_predictions"] = len(missing)
        summary["missing_ids"] = missing[:20]
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Score predictions on RadCheck-Bench-ES.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--data", default="data/test.jsonl", help="evaluation file (dev/test/extra)")
    ap.add_argument("--pred", required=True, help="JSONL of {id, output}")
    ap.add_argument("--out", help="write the JSON summary here as well")
    args = ap.parse_args()

    data = load_jsonl(args.data)
    predictions = {row["id"]: row.get("output", "") for row in load_jsonl(args.pred)}
    summary = score(data, predictions)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if args.out:
        Path(args.out).write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    if summary.get("missing_predictions"):
        print(
            f"warning: {summary['missing_predictions']} example(s) had no prediction",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
