# Prompt templates

The `.txt` files in this directory are the **exact** templates used to build the benchmark, kept
byte-identical to the version that produced `data/raw.jsonl`. They are in Spanish on purpose:
the models were prompted in Spanish because the reports, the labels and the findings are in
Spanish, and translating them would change what was generated.

This file is the English reference. Each summary says what the template does and which
placeholders it takes.

Placeholders use Python `str.format` syntax: `{nombre}`.

## Generation

### `generator_system.txt`

System prompt for both generation calls (clean report, then corruption).

> A Spanish radiologist persona writing synthetic reports for an NLP evaluation corpus.
> Hard rules: reports are invented from scratch, never adapted from real cases; European
> Spanish in real radiological register; no identifying data (at most "54-year-old patient");
> the conclusion summarises and rephrases the findings rather than copying them; answer with
> JSON only, no markdown.

### `clean_report.txt`

Writes one clean report for a composition spec. Placeholders: `modalidad`, `region`, `estilo`,
`min`, `max`, `dificultad`, `foco`.

> Asks for a single synthetic Spanish radiology report matching the spec: modality, anatomical
> region, one of four writing styles (A one paragraph with uppercase headers, B structured with
> line breaks, C narrative ending in IMPRESIÓN DIAGNÓSTICA, D telegraphic with abbreviations),
> a mandatory word band, and difficulty. Content requirements: 2–5 findings with anatomical
> location and measurements, a findings block and a separate conclusion block, the conclusion
> restating the main findings in other words, and no internal inconsistency anywhere. The
> `{foco}` slot carries the slice-specific requirement (see below). Returns
> `{"informe_limpio": "..."}`.

`{foco}` is filled in code, per slice:

- clean ordinary: make two findings appear in both the findings and the conclusion with the
  same side, polarity and number;
- clean hard negative: instantiate the named pattern (different sides for different findings,
  asymmetric bilateral finding, negation and assertion about different structures, the same
  number for different structures, comparison with a previous study, unlateralised organs) and
  state explicitly that the report must contain no contradiction;
- error slices: use the target type on one finding and mention it again in the conclusion,
  rephrased, so it appears exactly twice.

### `corrupt.txt`

Introduces the single minimal edit for the three scored types. Placeholders: `slice`,
`ubicacion`, `direccion`, `variante`, `dificultad`, `informe`.

> Receives an already written clean report and must introduce **exactly one** internal
> inconsistency of the requested type, with a minimal edit. It defines laterality, negation and
> measurement (with the four measurement variants: unit swap, ×10, digit slip, decimal slip),
> gives the required distance between the two mentions per difficulty, and then imposes:
> the finding must appear twice; `original` is 1–4 literal words that occur **once** in the
> report; `nuevo` replaces it and differs in 1–2 words; `contraparte` is 3–12 literal words from
> the *other* mention and must not overlap; the contradiction must be verifiable from the text
> alone; no other inconsistency; one-sentence explanation naming both places. Negation rewrites
> must stay grammatical. Returns `{original, nuevo, contraparte, explicacion}`.

Note the model never writes `fragmento`: the pipeline derives it in code from the actual edit,
so it is always an exact substring of the corrupted report.

### `corrupt_discordancia.txt` (extra track)

> Drops a relevant finding from the conclusion. The edit is a **deletion**, so `nuevo` is the
> empty string; `original` must be a unique literal mention in the conclusion; `contraparte`
> points at the now-orphaned finding in the findings block.

### `corrupt_transcripcion.txt` (extra track)

> Introduces one plausible speech-recognition word swap ("hilio" → "filio", "ecogénico" →
> "hecogénico"). The word must occur exactly twice, the edit changes one occurrence, and the
> other occurrence keeps the correct spelling so the error is detectable by internal comparison.

## Verification

### `checker_system.txt` and `checker_user.txt`

Used by the independent pass: a second model from a different family receives **only** the
report text and a prompt that is deliberately different from the evaluation system prompt.

> Defines the three scored classes, lists what must **not** be counted (different findings on
> different sides, bilateral findings, negation and assertion about different structures, the
> same number for different structures, comparison with a previous study, unlateralised organs,
> omissions, typos), and asks for
> `{"incoherencias": [{"tipo", "cita", "motivo"}], "comentario"}`. The user template wraps the
> report in `<<< >>>` delimiters.

## Evaluation

### `system_prompt.txt`

The **evaluation** system prompt, byte-identical to the one embedded in every item of
`data/{dev,test,extra}.jsonl` as `prompt[0].content` (verified by test). Spanish by nature: it
is the instruction the scored model receives.

> Tells the assistant it reviews Spanish radiology reports before signing, defines the three
> inconsistency types, forbids clinical judgement and diagnosis suggestions, and specifies the
> exact JSON answer format, including `{"errores": []}` for clean reports.
