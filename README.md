# RABCP anonymous reproducibility package

This repository provides the reproducibility materials for the IJSEKE revision. Cite a fixed commit URL when referring to these materials in the manuscript or rebuttal.

## What is included

- `code/BAE.py`, `code/generate_dataset.py`, and `code/实验/仿真数据实验/`: the original Bayesian estimator, deterministic synthetic-data generator, and original synthetic experiment scripts. These scripts use the simulated observed level as input; they do not assess extraction of L/C/G from prose.
- `code/original_scoring_reference/`: the original question extraction/scoring source for inspection. It requires an external OpenAI-compatible model and the original project input layout; it is not an offline reproduction entry. The old real-profile entry had a silent fallback algorithm and is excluded. The frozen outputs of that run are in `data/question_observations_870.jsonl`.
- `code/original_full_grid/`: the complete finite-grid study using the original four stationary-noise and five state-path generators. Every declared combination is evaluated (10,126 method/suite/flag/configuration entries); saved results and verification records are under `results/original_full_grid/`. The earlier 64-candidate sampled search on a different continuous-state generator remains separately archived under `results/simulation/`.
- `data/real_questions_870_redacted.jsonl`: 870 public Stack Overflow questions from 87 accounts, with a stable pseudonym for each sampled account, question IDs, source links, and author links. Emails, credential-shaped strings, and usernames in home paths are masked. The public post authors are not manuscript authors.
- `data/question_observations_870.jsonl`: archived automated observations used for the real-history experiment. These are machine outputs, not independently verified proficiency labels.
- `data/human_lcg_200.csv`: one row per reviewed question. The `archived_` columns contain the original Qwen scores used in the real-history profiles. The `revised_` columns contain DeepSeek scores under the revised rubric. The `human_reviewed_` columns contain the reference labels finalized by an author and a second reviewer after inspecting the posts and model suggestions. Twenty-five of these questions were used during development of the revised prompt. Section 5.3 compares both archived and revised scores against the shared reviewed labels.
- `data/answer_prompts_redacted/` and `data/answer_outputs_redacted/`: 40 target questions × three B/E/F answer conditions, including all 120 saved prompts and 120 saved outputs. B supplies full prior questions; E supplies selected source excerpts; F supplies the same excerpts and the archived RABCP profile. Text was masked after the API runs. No API key is included.
- [Final Table 13 data](results/table13_cases.csv) classify a single explanatory point per pair and give API input counts. The CSV includes the reviewed point in English and the archived Chinese comparison notes for all 31 targets with selected excerpts. The nine other targets are counted separately. The [earlier preference tally](results/team_consensus_80.md) was withdrawn and is preserved for provenance.

## Quick verification (standard library only)

Use Python 3.10 or later from a freshly extracted package root. Run `python3 code/verify_release.py` before running the experiment scripts. It checks the release hashes, the 120 API token counts and the Table 13 group totals. Then run `python3 code/reproduce_cached.py`. It checks data counts, joins, B/E/F coverage, and reports unweighted Cohen’s kappa for each dimension of both scorers against the reviewed labels. For the revised scorer the expected L/C/G values are 0.551, 0.299 and 0.638, with 462 of 600 dimension scores matching exactly and 138 one point apart. Run `python3 code/reproduce_real_profiles.py` to recompute 87 ten-question profiles from frozen observations; this writes `results/real_profiles_recomputed.csv`.

## Recreate the synthetic dataset

From the package root, run `python3 code/generate_dataset.py --output code/data/合成数据集.json --meta-output code/data/合成数据集_元信息.json`. The generator seed is fixed at 20260526 by default. The metadata timestamp changes between runs; the generated question records are deterministic for the same parameters. The original experiment scripts expect `code/data/合成数据集.json`. For example, run `python3 code/实验/仿真数据实验/状态估计实验.py` after generation. These scripts write result CSVs beside themselves.

The complete-grid study needs NumPy (`pip install -r requirements.txt`). Run `python3 code/original_full_grid/verify_core.py` for a lightweight scalar/vectorized implementation check. Run `python3 code/original_full_grid/run_grid.py --output results_verified` to reproduce the complete search, then `python3 code/original_full_grid/summarize_grid.py` to verify coverage, selection and replay. It uses one process, single-threaded BLAS and short pauses between candidates. Existing completed outputs are never overwritten. Saved outputs are under `results/original_full_grid/`. Earlier exploratory outputs are retained separately for provenance.

## Reproduce the manuscript tables

Run the commands from the repository root. For plots and Table 8 install the optional analysis dependencies with `python3 -m pip install -r requirements-manuscript.txt`. All commands below run offline. In a POSIX shell, set `SIM="code/实验/仿真数据实验"`. The simulated-data setup above is needed for the fixed-cohort scripts. Scripts in that folder write new results beside the script. Reference results for the added tables are in `results/manuscript_tables/`.

| Result | Command or input |
|---|---|
| Figure 2 | Run `python3 "$SIM/序列长度敏感性实验.py"` and `python3 "$SIM/噪声鲁棒性实验.py"`, then `python3 code/figure2.py --source "$SIM" --output figure2.pdf`. Omitting `--source` plots the archived fixed-cohort inputs. The right-hand panel uses the single 0.6 mixed-noise cohort. |
| Table 4 | `python3 "$SIM/multiseed_uncertainty_experiment.py"` rebuilds both noise ratios and the 50-seed intervals. |
| Table 5 | `python3 "$SIM/model_misspecification_experiment.py"` |
| Table 6 | Run the Table 5 and 7 scripts and `python3 "$SIM/matched_controls.py"`, then `python3 code/table6.py --source "$SIM"`. Use `python3 code/table6.py` to read the archived results. |
| Table 7 | `python3 "$SIM/conditional_recovery.py"` writes the seed-level counts and summary. Delay averages over recovered sequences. The older `state_switch_forgetting_experiment.py` includes a failure sentinel in its timing summary. |
| Table 8 | `python3 code/table8_associations.py --check-redacted-text`. The original scalar indicators and block order in `data/table8_indicators.csv` reproduce the three correlations, user-block confidence intervals and Holm-adjusted permutation tests. The additional check re-extracts indicators from public masked posts and reports differences. Resampling uses 10,000 draws and seed 20260714. |
| Tables 9–11 | Run `python3 "$SIM/hyperparameter_sensitivity_experiment.py"`, `python3 "$SIM/权重消融实验.py"` and `python3 "$SIM/risk_flag_error_sensitivity.py"`, respectively. The two deterministic Table 11 settings were run once each. The other five used 50 flag realizations. |
| Table 12 | From the extracted journal Supplement S1 run `python3 representation/reproduce_table12.py`. The supplement also includes the projection-coefficient sensitivity script. |
| Table 13 and follow-up | `python3 code/verify_release.py` recomputes the Table 13 totals. `python3 code/replay_answer_profiles.py --show U086` rebuilds the five-question profile from archived L/C/G, renders the depth instructions and checks all 40 combined prompts. With `--supplement /path/to/Supplement_S1` it additionally checks the 27 full-precision stage distributions and the 27 executed follow-up instructions against the journal supplement. |

### Scoring and answer inputs

The [v3 scorer system prompt](code/revised_scoring/system_prompt.txt) is the exact system text used for the 200 revised scores. [The rubric](code/revised_scoring/rubric.md) was logged separately. [Protocol records](data/scoring_protocol.csv) identify the 25 prompt-development cases and the remaining 175, with a digest of each original user prompt. `python3 code/revised_scoring/build_request.py --title "Example" --body body.txt` formats a request locally using the supplied body and verified image notes. Masked copies may have different input hashes. The 200 saved outputs determine the reported agreement numbers.

The 87 ten-question profiles use frozen observation distributions, which include intermediate rounding. The answer study computes the kernel from each of the five historical L/C/G triples at full precision, updates with window 5, weight 0.75 and no forgetting, then formats the stages and mean to three decimals. The later 27-target comparison additionally selects guided, standard or compact depth before formatting. Both experiments use the current question and the same selected excerpts in each E/F comparison.

## Provenance, limits, and release check

Question URLs and public author profile URLs provide per-post attribution. The archived question text is adapted by redaction. Stack Overflow user contributions are governed by CC BY-SA 3.0 or 4.0 for the dates in this collection; the applicable license for each revision is shown in its post timeline. See https://stackoverflow.com/help/licensing , https://creativecommons.org/licenses/by-sa/3.0/ , and https://creativecommons.org/licenses/by-sa/4.0/ . Source posts can change after the frozen snapshot; the archived text is the experiment input. Redaction can alter small parts of a question. Do not reconstruct masked content.

The 120 answer generations used an external model. Their saved prompts and outputs make the comparison inspectable without an API key; rerunning API generation may differ by model version or service behavior. `MANIFEST.csv` lists checksums of package contents, and `AUDIT.md` records an automated identity/secret scan. Both are release aids, not a substitute for final human inspection. Before journal resubmission, verify that the repository is publicly accessible without signing in and cite a fixed commit URL in the manuscript and rebuttal.
