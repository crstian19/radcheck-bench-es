# Changelog

All notable changes to RadCheck-Bench-ES are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-10-31

First release. The repository is private; the benchmark data is frozen at this version.

### Added

- **460 items**, all synthetic, in European Spanish:
  - 400 main items — 100 clean ordinary, 100 clean hard negatives, 67 `lateralidad`,
    67 `negacion`, 66 `medida` — split into `dev` (60) and `test` (340);
  - 60 extra-track items — 30 `discordancia` and 30 `transcripcion` — reported separately
    because they are not trained for and are not scored in the main result.
- Five modalities (X-ray, CT, MRI, ultrasound, mammography), seven anatomical regions, four
  writing styles at 25% each, 60–425 words (32% over 250), three difficulty levels.
- Six hard-negative patterns, 12–22 items each: different sides for different findings,
  asymmetric bilateral findings, negation and assertion about different structures, the same
  number for different structures, comparison with a previous study, unlateralised organs
  next to side words.
- `evaluate/score.py`: a standalone scorer with no dependency outside the standard library.
  Type must match and the predicted fragment must overlap the gold span or its counterpart;
  reports precision, recall, F1 overall and per type, false-alarm rate on clean reports,
  detection rate and invalid-JSON rate.
- `evaluate/run_openai.py`: runs any OpenAI-compatible endpoint over the test set and writes a
  predictions file for the scorer.
- `report/report.html`: a self-contained web report with the composition, the acceptance
  criteria, all 460 items and the rejected ones.
- `data/SHA256SUMS`: checksums for the shipped data files.

### Validation

- `scripts/validate.py` passes on 460/460 items (exact substrings, the corrupted report differs
  from the clean one only inside the labelled fragment, 1–4 token edits, no fragments that
  merely rewrite the counterpart, no duplicates, word band and style markers respected).
- Independent cross-family check (a Qwen model against the generator): 387/400 main-track labels agreed (96.8%).
  All 73 disagreements are published in `data/review.jsonl` with the reason.
- A perfect-oracle run scores F1 = 1.0 on `test`, which confirms the gold spans line up with
  the scoring rule.

### Notes

- No CARES text and no real patient data. The rule-based injector from the training pipeline was
  not used: corruptions come from model calls with their own prompts.
- Data licensed CC BY 4.0, code MIT.
