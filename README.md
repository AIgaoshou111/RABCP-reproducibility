# RABCP anonymous reproducibility package

This repository provides the reproducibility materials for the IJSEKE revision. Cite a fixed commit URL when referring to these materials in the manuscript or rebuttal.

## What is included

- `code/BAE.py`, `code/generate_dataset.py`, and `code/实验/仿真数据实验/`: the original Bayesian estimator, deterministic synthetic-data generator, and original synthetic experiment scripts. These scripts use the simulated observed level as input; they do not assess extraction of L/C/G from prose.
- `code/original_scoring_reference/`: the original question extraction/scoring source for inspection. It requires an external OpenAI-compatible model and the original project input layout; it is not an offline reproduction entry. The old real-profile entry had a silent fallback algorithm and is excluded. The frozen outputs of that run are in `data/question_observations_870.jsonl`.
- `code/original_full_grid/`: the complete finite-grid study using the original four stationary-noise and five state-path generators. Every declared combination is evaluated (10,126 method/suite/flag/configuration entries); saved results and verification records are under `results/original_full_grid/`. The earlier 64-candidate sampled search on a different continuous-state generator remains separately archived under `results/simulation/`.
- `data/real_questions_870_redacted.jsonl`: 870 public Stack Overflow questions from 87 accounts, with a stable pseudonym for each sampled account, question IDs, source links, and author links. Emails, credential-shaped strings, and usernames in home paths are masked. The public post authors are not manuscript authors.
- `data/question_observations_870.jsonl`: archived automated observations used for the real-history experiment. These are machine outputs, not independently verified proficiency labels.
- `data/human_lcg_200.csv`: 200 questions, archived L/C/G scores, and human-reviewed reference labels. The labels began as model-assisted drafts and were checked by an author and another human reviewer. The reported kappa compares archived automatic scores with these jointly reviewed labels.
- `data/answer_prompts_redacted/` and `data/answer_outputs_redacted/`: 40 target questions × three B/E/F answer conditions, including all 120 saved prompts and 120 saved outputs. B supplies full prior questions; E supplies selected source excerpts; F supplies the same excerpts and the archived RABCP profile. Text was masked after the API runs. No API key is included.
- `results/`: saved numeric outputs and team-consensus answer-suitability assessments. The answer assessment concerns preservation of necessary content, useful adaptation to historical evidence, and avoiding unnecessary or unsupported additions. It is not a model-correctness rate.

## Quick verification (standard library only)

From the package root, run `python3 code/reproduce_cached.py`. It checks data counts, joins, B/E/F coverage, and recomputes agreement with the 200 human-reviewed labels. Run `python3 code/reproduce_real_profiles.py` to recompute 87 ten-question profiles from frozen observations; this writes `results/real_profiles_recomputed.csv`.

## Recreate the synthetic dataset

From the package root, run `python3 code/generate_dataset.py --output code/data/合成数据集.json --meta-output code/data/合成数据集_元信息.json`. The generator seed is fixed at 20260526 by default. The metadata timestamp changes between runs; the generated question records are deterministic for the same parameters. The original experiment scripts expect `code/data/合成数据集.json`. For example, run `python3 code/实验/仿真数据实验/状态估计实验.py` after generation. These scripts write result CSVs beside themselves.

The complete-grid study needs NumPy (`pip install -r requirements.txt`). Run `python3 code/original_full_grid/verify_core.py` for a lightweight scalar/vectorized implementation check. Run `python3 code/original_full_grid/run_grid.py --output results_verified` to reproduce the complete search, then `python3 code/original_full_grid/summarize_grid.py` to verify coverage, selection and replay. It uses one process, single-threaded BLAS and short pauses between candidates. Existing completed outputs are never overwritten. Saved outputs are under `results/original_full_grid/`. Earlier exploratory outputs are retained separately for provenance.

## Provenance, limits, and release check

Question URLs and public author profile URLs provide per-post attribution. The archived question text is adapted by redaction. Stack Overflow user contributions are governed by CC BY-SA 3.0 or 4.0 for the dates in this collection; the applicable license for each revision is shown in its post timeline. See https://stackoverflow.com/help/licensing , https://creativecommons.org/licenses/by-sa/3.0/ , and https://creativecommons.org/licenses/by-sa/4.0/ . Source posts can change after the frozen snapshot; the archived text is the experiment input. Redaction can alter small parts of a question. Do not reconstruct masked content.

The 120 answer generations used an external model. Their saved prompts and outputs make the comparison inspectable without an API key; rerunning API generation may differ by model version or service behavior. `MANIFEST.csv` lists checksums of package contents, and `AUDIT.md` records an automated identity/secret scan. Both are release aids, not a substitute for final human inspection. Before journal resubmission, verify that the repository is publicly accessible without signing in and cite a fixed commit URL in the manuscript and rebuttal.
