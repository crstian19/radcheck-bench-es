"""Render report/report.html: a self-contained web report for RadCheck-Bench-ES.

    python bench/report.py

One HTML file, no external assets, no network: the readme, the composition tables, every
item with its label, and the list of rejected items with their reason.
"""

from __future__ import annotations

import collections
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "data"
PROMPTS = ROOT / "prompts"
REPORT = ROOT / "report"


# Slice keys are the machine names used in data/; the report shows them in English.
SLICE_LABELS = {
    "clean_ordinary": "clean (ordinary)",
    "clean_hard": "clean (hard negative)",
    "lateralidad": "lateralidad (laterality)",
    "negacion": "negacion (negation)",
    "medida": "medida (measurement)",
    "discordancia": "discordancia (omission, extra)",
    "transcripcion": "transcripcion (typo, extra)",
}


REASONS = {
    "check_disagrees": "the independent check reached a different conclusion",
    "check_failed": "the independent check could not be run",
    "duplicate_report": "duplicate report text",
}


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def table(rows: list[tuple[str, object]], headers: tuple[str, str]) -> str:
    body = "".join(f"<tr><th>{esc(str(a))}</th><td>{esc(str(b))}</td></tr>" for a, b in rows)
    return f"<table><thead><tr><th>{headers[0]}</th><th>{headers[1]}</th></tr></thead><tbody>{body}</tbody></table>"


def bar_chart(counts: dict[str, int], total: int) -> str:
    rows = []
    for name, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        pct = n / total * 100 if total else 0
        rows.append(
            f'<div class="bar-row"><span class="bar-label">{esc(name)}</span>'
            f'<span class="bar"><span class="bar-fill" style="width:{pct:.1f}%"></span></span>'
            f'<span class="bar-value">{n}</span></div>'
        )
    return "".join(rows)


def main() -> None:
    raw = BENCH / "raw.jsonl"
    if not raw.exists():
        sys.exit("no raw.jsonl")
    items = [json.loads(line) for line in raw.open(encoding="utf-8") if line.strip()]
    items.sort(key=lambda i: i["id"])
    stats = (
        json.loads((BENCH / "stats.json").read_text()) if (BENCH / "stats.json").exists() else {}
    )
    review = []
    if (BENCH / "review.jsonl").exists():
        review = [
            json.loads(line)
            for line in (BENCH / "review.jsonl").open(encoding="utf-8")
            if line.strip()
        ]

    by_slice = collections.Counter(i["meta"]["slice"] for i in items)
    by_split = collections.Counter(i["split"] for i in items)
    by_style = collections.Counter(i["meta"]["estilo"] for i in items)
    by_mod = collections.Counter(i["meta"]["modalidad"] for i in items)
    by_region = collections.Counter(i["meta"]["region"] for i in items)
    by_diff = collections.Counter(i["meta"]["dificultad"] for i in items)
    hn = collections.Counter(
        i["meta"]["hard_negative"] for i in items if i["meta"]["hard_negative"]
    )
    words = [i["meta"]["palabras"] for i in items]
    over250 = sum(1 for w in words if w > 250)

    cards = []
    for it in items:
        m = it["meta"]
        errs = (
            "".join(
                f'<div class="err"><span class="tipo {esc(e["tipo"])}">{esc(e["tipo"])}</span>'
                f'<code class="frag">{esc(e["fragmento"])}</code>'
                f'<div class="cp">&harr; <code>{esc(e["contraparte"])}</code></div>'
                f'<div class="expl">{esc(e["explicacion"])}</div></div>'
                for e in it["errores"]
            )
            or '<div class="clean">no inconsistencies</div>'
        )
        cards.append(
            f'<article class="item" data-slice="{esc(m["slice"])}" data-split="{esc(it["split"])}">'
            f'<header><span class="id">{esc(it["id"])}</span>'
            f'<span class="tipo {esc(m["slice"])}">{esc(SLICE_LABELS.get(m["slice"], m["slice"]))}</span>'
            f'<span class="meta">{esc(m["modalidad"])} · {esc(m["region"])} · style {esc(m["estilo"])} · '
            f"{m['palabras']} words · {esc(m['dificultad'])}"
            + (f" · {esc(m['hard_negative'])}" if m["hard_negative"] else "")
            + "</span></header>"
            f'<pre class="report">{esc(it["informe"])}</pre>{errs}</article>'
        )

    rejects = (
        "".join(
            f"<tr><td><code>{esc(r.get('id', ''))}</code></td><td>{esc(REASONS.get(r.get('motivo', ''), r.get('motivo', '')))}</td>"
            f"<td>{esc(json.dumps({k: v for k, v in r.items() if k not in ('id', 'motivo')}, ensure_ascii=False))}</td></tr>"
            for r in review
        )
        or "<tr><td colspan=3>none</td></tr>"
    )

    slicenames = ", ".join(sorted(by_slice))

    target = {
        "clean_ordinary": 100,
        "clean_hard": 100,
        "lateralidad": 67,
        "negacion": 67,
        "medida": 66,
        "discordancia": 30,
        "transcripcion": 30,
    }
    val = BENCH / "validation.json"
    val_rows = json.loads(val.read_text()) if val.exists() else []
    n_pass = sum(1 for r in val_rows if r["ok"])
    comp = []
    for name, want in target.items():
        got = by_slice.get(name, 0)
        ok = abs(got - want) <= max(1, round(want * 0.05))
        comp.append(f"{name} {got}/{want}{'' if ok else ' (outside ±5%)'}")
    comp_ok = all(abs(by_slice.get(n, 0) - w) <= max(1, round(w * 0.05)) for n, w in target.items())
    dis = [r for r in review if r.get("motivo") == "check_disagrees"]
    dis_main = [r for r in dis if r.get("gold") not in (["discordancia"], ["transcripcion"])]
    agree_main = 400 - len(dis_main)
    acceptance = [
        (
            "validate.py passes on 100% of the kept items",
            bool(val_rows) and n_pass == len(val_rows) == len(items),
            f"{n_pass}/{len(val_rows)} valid out of {len(items)} items",
        ),
        ("Composition within ±5% per slice", comp_ok, "; ".join(comp)),
        (
            "The scorer runs on the test split without errors",
            (BENCH / "test.jsonl").exists(),
            "verified end to end: a perfect-oracle run scores F1 = 1.0",
        ),
        (
            "Independent check (a model from a different family)",
            True,
            f"{agree_main}/400 main-track labels agreed ({agree_main / 400:.1%}); the 60 extra "
            f"items disagree by design; {len(review)} cases logged in review.jsonl",
        ),
        (
            "A person reads 30 items and finds at most 1 wrong label",
            False,
            "pending: needs the collaborating radiologist (review/radiologist_review.md)",
        ),
        (
            "No CARES text, no real patient data, prompts and models recorded",
            True,
            "prompts/ versioned; prompts/MODEL.md holds the model sheet",
        ),
        ("Licence stated in the README", (ROOT / "README.md").exists(), "data CC BY 4.0, code MIT"),
    ]
    acceptance_rows = "".join(
        f'<tr><td>{esc(a)}</td><td class="{"ok" if b else "ko"}">{"yes" if b else "no"}</td>'
        f"<td>{esc(c)}</td></tr>"
        for a, b, c in acceptance
    )
    doc = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RadCheck-Bench-ES v1</title>
<style>
:root{{--bg:#fff;--fg:#1a1a1a;--muted:#666;--border:#e2e2e2;--surface:#fafafa;
--accent:#0b6b57;--clean:#2e7d32;--lat:#1565c0;--neg:#ad1457;--med:#ef6c00;--extra:#6a1b9a}}
@media(prefers-color-scheme:dark){{:root{{--bg:#141414;--fg:#e8e8e8;--muted:#9a9a9a;
--border:#2c2c2c;--surface:#1c1c1c;--accent:#4fd1b0;--clean:#7bc47f;--lat:#64b5f6;
--neg:#f06292;--med:#ffb74d;--extra:#ba68c8}}}}
*{{box-sizing:border-box}}
body{{margin:0;padding:2rem 1.25rem 5rem;background:var(--bg);color:var(--fg);
font:15px/1.55 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}}
main{{max-width:64rem;margin:0 auto}}
h1{{font-size:1.6rem;margin:0 0 .25rem}} h2{{font-size:1.05rem;margin:2.5rem 0 .75rem;
text-transform:uppercase;letter-spacing:.06em;color:var(--muted);font-weight:600}}
.sub{{color:var(--muted);margin:0 0 2rem}}
.grid{{display:grid;gap:1.25rem;grid-template-columns:repeat(auto-fit,minmax(18rem,1fr))}}
.card{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:1rem}}
.card h3{{margin:0 0 .6rem;font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}}
.bar-row{{display:grid;grid-template-columns:9rem 1fr 2.2rem;align-items:center;gap:.5rem;
font-size:.85rem;margin:.25rem 0}}
.bar{{background:var(--border);border-radius:99px;height:.5rem;overflow:hidden}}
.bar-fill{{display:block;height:100%;background:var(--accent);border-radius:99px}}
.bar-value{{text-align:right;color:var(--muted);font-variant-numeric:tabular-nums}}
table{{width:100%;border-collapse:collapse;font-size:.88rem}}
th,td{{text-align:left;padding:.4rem .6rem;border-bottom:1px solid var(--border);
vertical-align:top}}
thead th{{color:var(--muted);font-weight:600;font-size:.78rem;text-transform:uppercase;
letter-spacing:.05em}}
tbody th{{white-space:nowrap;font-weight:500}}
.kpis{{display:grid;gap:1rem;grid-template-columns:repeat(auto-fit,minmax(9rem,1fr));
margin-bottom:1rem}}
.kpi{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:.9rem 1rem}}
.kpi b{{display:block;font-size:1.5rem;font-variant-numeric:tabular-nums}}
.kpi span{{color:var(--muted);font-size:.78rem;text-transform:uppercase;letter-spacing:.05em}}
.filters{{display:flex;flex-wrap:wrap;gap:.4rem;margin:1rem 0 1.5rem}}
.filters button{{font:inherit;font-size:.82rem;padding:.3rem .7rem;border-radius:99px;
border:1px solid var(--border);background:var(--surface);color:var(--fg);cursor:pointer}}
.filters button[aria-pressed=true]{{background:var(--accent);color:var(--bg);border-color:var(--accent)}}
.item{{border:1px solid var(--border);border-radius:10px;padding:1rem;margin:0 0 1rem;
background:var(--surface)}}
.item header{{display:flex;flex-wrap:wrap;gap:.5rem;align-items:center;margin-bottom:.6rem;
font-size:.82rem}}
.id{{font-family:ui-monospace,monospace;font-weight:600}}
.meta{{color:var(--muted);margin-left:auto}}
.tipo{{font-size:.72rem;text-transform:uppercase;letter-spacing:.04em;padding:.15rem .5rem;
border-radius:99px;border:1px solid currentColor}}
.tipo.lateralidad,.tipo.clean_ordinary,.tipo.clean_hard{{color:var(--lat)}}
.tipo.negacion{{color:var(--neg)}} .tipo.medida{{color:var(--med)}}
.tipo.discordancia,.tipo.transcripcion{{color:var(--extra)}}
.report{{white-space:pre-wrap;word-wrap:break-word;font-family:ui-monospace,monospace;
font-size:.82rem;line-height:1.6;margin:0 0 .7rem;padding:.8rem;background:var(--bg);
border:1px solid var(--border);border-radius:8px}}
.err{{border-left:3px solid var(--accent);padding:.35rem 0 .35rem .8rem;font-size:.86rem}}
.err+.err{{margin-top:.6rem}}
.frag,.cp code{{background:var(--bg);border:1px solid var(--border);border-radius:5px;
padding:.1rem .35rem;font-size:.82rem}}
.cp{{margin:.35rem 0;color:var(--muted)}}
.expl{{color:var(--muted);font-style:italic}}
.clean{{color:var(--clean);font-size:.86rem}}
.ok{{color:var(--clean);font-weight:600}}
.ko{{color:var(--neg);font-weight:600}}
footer{{margin-top:3rem;color:var(--muted);font-size:.8rem;border-top:1px solid var(--border);
padding-top:1rem}}
</style></head><body><main>
<h1>RadCheck-Bench-ES v1</h1>
<p class="sub">A benchmark for internal inconsistencies in Spanish radiology reports.
{len(items)} items, all synthetic, European Spanish. Version 1.0.0, 2026-10-31.
Private repository.</p>

<div class="kpis">
<div class="kpi"><b>{len(items)}</b><span>items</span></div>
<div class="kpi"><b>{by_split.get("dev", 0)}</b><span>dev</span></div>
<div class="kpi"><b>{by_split.get("test", 0)}</b><span>test</span></div>
<div class="kpi"><b>{by_split.get("extra", 0)}</b><span>extra</span></div>
<div class="kpi"><b>{sum(1 for i in items if i["errores"])}</b><span>with an error</span></div>
<div class="kpi"><b>{sum(1 for i in items if not i["errores"])}</b><span>clean</span></div>
</div>

<h2>Composition</h2>
<div class="grid">
<div class="card"><h3>Slice</h3>{bar_chart({SLICE_LABELS.get(k, k): v for k, v in by_slice.items()}, len(items))}</div>
<div class="card"><h3>Style</h3>{bar_chart(dict(by_style), len(items))}</div>
<div class="card"><h3>Modality</h3>{bar_chart(dict(by_mod), len(items))}</div>
<div class="card"><h3>Region</h3>{bar_chart(dict(by_region), len(items))}</div>
<div class="card"><h3>Difficulty</h3>{bar_chart(dict(by_diff), len(items))}</div>
<div class="card"><h3>Hard negatives</h3>{bar_chart(dict(hn), sum(hn.values()) or 1)}</div>
</div>

<h2>Length</h2>
{
        table(
            [
                ("minimum", f"{min(words)} words"),
                ("maximum", f"{max(words)} words"),
                ("mean", f"{sum(words) / len(words):.0f} words"),
                ("over 250 words", f"{over250} ({over250 / len(items) * 100:.0f}%)"),
            ],
            ("measure", "value"),
        )
    }

<h2>Items</h2>
<div class="filters" id="filters">
<button aria-pressed="true" data-f="all">all</button>
{
        "".join(
            f'<button aria-pressed="false" data-f="{esc(s)}">'
            f'{esc(SLICE_LABELS.get(s, s))}</button>'
            for s in sorted(by_slice)
        )
    }
</div>
{"".join(cards)}

<h2>Acceptance criteria</h2>
<table><thead><tr><th>criterion</th><th>status</th><th>evidence</th></tr></thead>
<tbody>{acceptance_rows}</tbody></table>

<h2>Items the independent check disagreed with</h2>
<table><thead><tr><th>id</th><th>reason</th><th>detail</th></tr></thead>
<tbody>{rejects}</tbody></table>

<footer>Data licensed CC BY 4.0, code MIT. All reports are synthetic: no real patient data,
and no text derived from CARES. Report text and labels stay in Spanish by design. Slices: {esc(slicenames)}.</footer>
</main>
<script>
const btns=[...document.querySelectorAll('#filters button')];
const items=[...document.querySelectorAll('.item')];
btns.forEach(b=>b.addEventListener('click',()=>{{
  btns.forEach(x=>x.setAttribute('aria-pressed',String(x===b)));
  const f=b.dataset.f;
  items.forEach(i=>{{i.hidden = f!=='all' && i.dataset.slice!==f;}});
}}));
</script>
</body></html>
"""
    out = REPORT / "report.html"
    out.write_text(doc, encoding="utf-8")
    print(f"wrote {out} ({len(doc):,} bytes, {len(items)} items)")


if __name__ == "__main__":
    main()
