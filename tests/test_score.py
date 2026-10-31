"""Tests for the standalone scorer.

Three handcrafted predictions with hand-checked numbers, plus the parsing edge cases the
matching rule depends on. Run with ``uv run pytest``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evaluate"))

from score import Scores, locate, matches, parse_output, score  # noqa: E402

# --- fixture: one laterality error and two clean reports -------------------------------

CORRUPTED = (
    "HALLAZGOS: quiste de 18 mm en riñón izquierdo. "
    "CONCLUSIÓN: quiste renal derecho de 18 mm."
)
CLEAN_1 = "HALLAZGOS: hígado homogéneo. CONCLUSIÓN: sin hallazgos significativos."
CLEAN_2 = "HALLAZGOS: bazo de tamaño normal. CONCLUSIÓN: bazo normal."

FRAGMENT = "quiste renal derecho de 18 mm"
COUNTERPART = "quiste de 18 mm en riñón izquierdo"


def _example(item_id: str, report: str, gold: list[dict]) -> dict:
    return {
        "id": item_id,
        "prompt": [{"role": "system", "content": "s"}, {"role": "user", "content": report}],
        "gold": gold,
    }


def _gold_laterality() -> dict:
    start = CORRUPTED.index(FRAGMENT)
    cp = CORRUPTED.index(COUNTERPART)
    return {
        "tipo": "lateralidad",
        "fragmento": FRAGMENT,
        "explicacion": "conclusión vs hallazgos",
        "start": start,
        "end": start + len(FRAGMENT),
        "original": "izquierdo",
        "counterpart": [cp, cp + len(COUNTERPART)],
    }


def _data() -> list[dict]:
    return [
        _example("rcb-1", CORRUPTED, [_gold_laterality()]),
        _example("rcb-2", CLEAN_1, []),
        _example("rcb-3", CLEAN_2, []),
    ]


def _predictions() -> dict[str, str]:
    return {
        # Quotes the COUNTERPART, not the changed span: must still count as a hit.
        "rcb-1": json.dumps(
            {"errores": [{"tipo": "lateralidad", "fragmento": COUNTERPART,
                          "explicacion": "hallazgos en el lado izquierdo"}]},
            ensure_ascii=False,
        ),
        # Clean report, correct answer.
        "rcb-2": '{"errores": []}',
        # Clean report, spurious flag: false alarm.
        "rcb-3": json.dumps(
            {"errores": [{"tipo": "lateralidad", "fragmento": "bazo de tamaño normal",
                          "explicacion": "falso positivo"}]},
            ensure_ascii=False,
        ),
    }


def test_numbers() -> None:
    """One TP (via counterpart), one FP, no FN; 3 examples, 1 corrupted, 2 clean."""
    summary = score(_data(), _predictions())

    assert summary["examples"] == 3
    assert summary["overall"] == {
        "precision": 0.5,   # 1 TP / (1 TP + 1 FP)
        "recall": 1.0,      # 1 TP / (1 TP + 0 FN)
        "f1": 0.667,        # 2 * 0.5 * 1.0 / 1.5
        "support": 1,
    }
    assert summary["per_type"]["lateralidad"] == {
        "precision": 0.5, "recall": 1.0, "f1": 0.667, "support": 1
    }
    assert summary["per_type"]["negacion"] == {
        "precision": 0.0, "recall": 0.0, "f1": 0.0, "support": 0
    }
    assert summary["false_alarm_rate"] == 0.5     # 1 of 2 clean reports flagged
    assert summary["detection_rate"] == 1.0       # the one corrupted report was flagged
    assert summary["invalid_json_rate"] == 0.0


def test_counterpart_overlap_is_a_hit() -> None:
    gold = _gold_laterality()
    pred = {"tipo": "lateralidad", "fragmento": COUNTERPART}
    assert matches(pred, gold, CORRUPTED)


def test_wrong_type_never_matches() -> None:
    gold = _gold_laterality()
    pred = {"tipo": "medida", "fragmento": FRAGMENT}
    assert not matches(pred, gold, CORRUPTED)


def test_invalid_json_counts_as_no_prediction() -> None:
    scores = Scores()
    scores.add(CORRUPTED, [_gold_laterality()], parse_output("no json here"))
    summary = scores.summary()
    assert summary["invalid_json_rate"] == 1.0
    assert summary["per_type"]["lateralidad"]["recall"] == 0.0
    assert summary["detection_rate"] == 0.0


def test_parse_output_tolerates_prose_and_thinking() -> None:
    raw = 'Here you go: <think>maybe</think>{"errores": [{"tipo": "medida"}]} -- done'
    assert parse_output(raw) == [{"tipo": "medida"}]


def test_locate_is_case_and_whitespace_tolerant() -> None:
    report = "un nódulo  de 9 mm"
    assert locate("NÓDULO de 9 mm", report) is not None
    assert locate("ausente", report) is None
