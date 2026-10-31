# Generation provenance

Every prompt template in this directory is versioned with the benchmark. This file records what
produced `data/raw.jsonl`, so a run can be audited or repeated.

## Generator (clean reports + corruptions)

| Field | Value |
|---|---|
| Model | a general-purpose LLM served through an OpenAI-compatible endpoint (`RADCHECK_BENCH_MODEL`) |
| Temperature | 0.75, +0.05 per retry |
| Seed | per item: `13 + crc32(id) + 7919 * attempt`. A single fixed seed made the server replay the same report for different specs and produced duplicates; the per-item seed removes that. |
| Thinking | disabled per call: `chat_template_kwargs.enable_thinking=false` |
| Response format | `{"type": "json_object"}` |
| Max tokens | 4000 |
| Calls per item | 2 for error items and the extra track (clean report, then the edit), 1 for clean items |

The endpoint (`RADCHECK_BENCH_BASE_URL`) and the generator's model id are not recorded here. The
sampling parameters above are the part of the run the pipeline controls.

## Independent checker

| Field | Value |
|---|---|
| Model | Qwen 3.8 Flash |
| Model id | `qwen3.8-flash` (published without the serving account prefix) |
| Temperature | 0.1, up to 3 attempts |
| Prompt | `checker_system.txt` + `checker_user.txt`; it receives **only** the report text |
| Agreement | 387/400 main-track labels (96.8%); 60/60 extra-track disagreements are by design |

The checker is a **different model family** from the generator on purpose. A cross-family model
keeps the second opinion independent in the way that matters most: different weights, different
failure modes. Every disagreement is listed in `data/review.jsonl`; none was dropped silently.

## Prompt files

| File | Used for |
|---|---|
| `generator_system.txt` | system prompt for both generation calls |
| `clean_report.txt` | clean report, one per spec |
| `corrupt.txt` | the single minimal edit (`lateralidad` / `negacion` / `medida`) |
| `corrupt_discordancia.txt` | extra track: finding dropped from the conclusion |
| `corrupt_transcripcion.txt` | extra track: speech-recognition word swap |
| `checker_system.txt`, `checker_user.txt` | independent verification |
| `system_prompt.txt` | the evaluation prompt embedded in every data item |

English summaries of each template are in [`PROMPTS.md`](./PROMPTS.md).

## Not used, by design

- **CARES** (`SINAI/CARES`) was never opened, downloaded or read. No text in this benchmark is
  derived from it. The optional 8-gram overlap check from the design spec therefore does not
  apply; only duplicate detection is used.
- **The rule-based injector** from the training project was not read or imported. Corruptions
  are model calls with their own prompt, so generated errors do not inherit the injector's
  eligibility rules. That independence is the point of the benchmark.

## Credentials

The API key is read from `RADCHECK_BENCH_API_KEY` at call time and is never written to a file, a log
or an output artefact. No key, token or private hostname is stored in this repository.
