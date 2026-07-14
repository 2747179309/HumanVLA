# T07C-B3 Traditional Trajectory Baselines

## Run identity

- Run ID: `20260714_T07C_B3_VALIDATION_SELECTION_001`
- Test Run ID: `20260714_T07C_B3_TEST_ONCE_001`
- Evaluation Run ID: `20260714_T07C_B3_TEST_EVALUATION_001`
- Date: 2026-07-14
- Scope: `pick_place_pilot_v1_E001` within-episode synthetic benchmark only
- Git baseline before run: `231fe97dc5788b0c5d40b677c0bf7f116b1b8182` (worktree already dirty)

## Purpose

Implement and compare corrupted-input/no-processing, Savitzky-Golay, causal One Euro, causal constant-velocity Kalman and causal confidence-weighted Kalman. No quality-aware, phase-preserving or bone-constrained method is included.

## Environment

- Python: system Python used by the project
- NumPy: 1.24.3
- SciPy: 1.11.1
- pandas: 2.0.3
- Matplotlib: 3.7.2
- `MPLCONFIGDIR=/tmp/humanvla_matplotlib` used because the default Matplotlib cache directory is not writable

## Inputs and frozen hashes

- Config: `configs/refinement/t07c_b3_baselines.json`
  - SHA-256: `0815fe96eb320bc5a64784965962ff441bd9c8cc5dea7e6e806f9d06c7bbdb16`
- B2 dataset: `data/trajectories/pick_place_pilot_v1_E001/synthetic_corruption_dataset.jsonl`
  - SHA-256: `ee84857e856986a43c2d8d24bc96ce6d1ad0fd2a3c9d06e2fd0599093b724d4e`
- Raw trajectory, used only to retrieve source OpenPose confidence:
  `data/trajectories/pick_place_pilot_v1_E001/raw_upper_limb_trajectory.jsonl`
  - SHA-256: `c29b2a66b2787aeed665d567e03a9b31acec8fbcce577c9bd1c58d57e3655506`
- Frozen B2 split counts: train 168, val 72, test 96

## Commands

Static and CLI checks:

```bash
python -m py_compile scripts/trajectory/run_traditional_baselines.py scripts/trajectory/tune_baseline_parameters.py scripts/trajectory/evaluate_refinement_baselines.py
python scripts/trajectory/run_traditional_baselines.py --help
MPLCONFIGDIR=/tmp/humanvla_matplotlib python scripts/trajectory/tune_baseline_parameters.py --help
MPLCONFIGDIR=/tmp/humanvla_matplotlib python scripts/trajectory/evaluate_refinement_baselines.py --help
```

Validation selection; this script did not retain or evaluate test rows:

```bash
MPLCONFIGDIR=/tmp/humanvla_matplotlib python scripts/trajectory/tune_baseline_parameters.py \
  --config configs/refinement/t07c_b3_baselines.json \
  --dataset data/trajectories/pick_place_pilot_v1_E001/synthetic_corruption_dataset.jsonl \
  --raw-trajectory data/trajectories/pick_place_pilot_v1_E001/raw_upper_limb_trajectory.jsonl \
  --output-search-csv results/trajectories/pick_place_pilot_v1_E001/b3_validation_parameter_search.csv \
  --output-selected-json results/trajectories/pick_place_pilot_v1_E001/b3_selected_parameters.json
```

The following command ran the frozen test split once. It also generated selected-method outputs for train and val for the 336-sample completeness audit:

```bash
MPLCONFIGDIR=/tmp/humanvla_matplotlib python scripts/trajectory/run_traditional_baselines.py \
  --config configs/refinement/t07c_b3_baselines.json \
  --dataset data/trajectories/pick_place_pilot_v1_E001/synthetic_corruption_dataset.jsonl \
  --raw-trajectory data/trajectories/pick_place_pilot_v1_E001/raw_upper_limb_trajectory.jsonl \
  --selected-parameters results/trajectories/pick_place_pilot_v1_E001/b3_selected_parameters.json \
  --output results/trajectories/pick_place_pilot_v1_E001/b3_all_split_predictions.jsonl \
  --test-audit results/trajectories/pick_place_pilot_v1_E001/b3_test_once_audit.json
```

Test reporting from the immutable prediction file:

```bash
MPLCONFIGDIR=/tmp/humanvla_matplotlib python scripts/trajectory/evaluate_refinement_baselines.py \
  --config configs/refinement/t07c_b3_baselines.json \
  --dataset data/trajectories/pick_place_pilot_v1_E001/synthetic_corruption_dataset.jsonl \
  --predictions results/trajectories/pick_place_pilot_v1_E001/b3_all_split_predictions.jsonl \
  --selected-parameters results/trajectories/pick_place_pilot_v1_E001/b3_selected_parameters.json \
  --test-audit results/trajectories/pick_place_pilot_v1_E001/b3_test_once_audit.json \
  --output-csv results/trajectories/pick_place_pilot_v1_E001/b3_test_results.csv \
  --output-summary results/trajectories/pick_place_pilot_v1_E001/b3_test_summary.json \
  --output-plot results/trajectories/pick_place_pilot_v1_E001/b3_baseline_comparison.png
```

## Parameters and validation selection

- Candidate counts: no-processing 1, SG 3, One Euro 16, Kalman CV 9, confidence-weighted Kalman 18; total 47.
- Train was recorded as development diagnostics only. Every candidate was evaluated on val and ranked by the preregistered val score.
- SG: `window_length=7`, `polyorder=2`; val score 0.051879.
- One Euro: `min_cutoff_hz=5.0`, `beta=0.0`, `derivative_cutoff_hz=1.0`; val score 0.059751.
- Kalman CV: acceleration noise std 8.0 norm/s2, measurement noise std 0.005 norm, initial velocity std 1.0 norm/s; val score 0.058598.
- Confidence-weighted Kalman: acceleration noise std 8.0 norm/s2, base measurement std 0.005 norm, confidence power 1.0, minimum confidence 0.05, initial velocity std 1.0 norm/s; val score 0.059038.

## Quantitative test results

Test contains 96 samples and 480 sample-method rows. The primary metric includes the preregistered explicit penalty for missing predictions; formal position RMSE remains null when no prediction exists.

| Method | Penalized corrupted RMSE norm | Clean displacement norm | Max error norm | Velocity RMSE norm/s | Acceleration RMSE norm/s2 | Jerk RMSE norm/s3 | Coverage |
|---|---:|---:|---:|---:|---:|---:|---:|
| Savitzky-Golay | 0.058489 | 0.022568 | 0.075425 | 0.837135 | 25.645557 | 1153.780662 | 1.000000 |
| One Euro | 0.062395 | 0.019928 | 0.084355 | 0.925742 | 37.632063 | 1751.252304 | 1.000000 |
| Confidence-weighted Kalman | 0.081717 | 0.009164 | 0.104947 | 1.458585 | 59.787441 | 2710.698358 | 1.000000 |
| Kalman CV | 0.082074 | 0.008250 | 0.105267 | 1.485756 | 61.250344 | 2786.267068 | 1.000000 |
| Corrupted input | 0.328990 | 0.000000 | 0.131417 | 2.179180 | 96.476504 | 4654.033618 | 0.927083 |

By corruption, primary RMSE norm:

| Method | Gaussian | Burst | Drift | Missing |
|---|---:|---:|---:|---:|
| SG | 0.028019 | 0.115689 | 0.079102 | 0.011148 |
| One Euro | 0.029835 | 0.125488 | 0.072866 | 0.021391 |
| Kalman CV | 0.039944 | 0.178882 | 0.090943 | 0.018528 |
| Confidence-weighted Kalman | 0.039409 | 0.178187 | 0.090959 | 0.018311 |
| Corrupted input | 0.044551 | 0.180597 | 0.090810 | 1.000000 penalty |

- Phase-boundary shift: 0 defined samples. All B2 windows contain one phase, so this metric is null/not applicable rather than zero.
- Real-motion attenuation may be negative; negative means output path amplification, not negative error.
- No ordinary baseline used truth, a synthetic corruption mask or a manual mask as filter input.

## Outputs

- `results/trajectories/pick_place_pilot_v1_E001/b3_validation_parameter_search.csv` (47 rows)
- `results/trajectories/pick_place_pilot_v1_E001/b3_selected_parameters.json`
- `results/trajectories/pick_place_pilot_v1_E001/b3_test_once_audit.json`
- `results/trajectories/pick_place_pilot_v1_E001/b3_all_split_predictions.jsonl` (1680 rows)
- `results/trajectories/pick_place_pilot_v1_E001/b3_test_results.csv` (480 rows)
- `results/trajectories/pick_place_pilot_v1_E001/b3_test_summary.json` (240 full-dimension groups)
- `results/trajectories/pick_place_pilot_v1_E001/b3_baseline_comparison.png`

Final output SHA-256:

- Search CSV: `c9416446b6682f94224c8cd8f2af8edb25b1cd4e90865694e63ba73e8db27605`
- Selected parameters: `dc3a471c78d7a2b4074fb812469be39bbcb6db78cea7c820933d843694e2ea09`
- Test-once audit: `71c19e10b8454fc53516d4d8f839f6587e3a068c36c370d99dd2f9b2d2a16ab2`
- All-split predictions: `86e31f7eba37583e98cabb5672196479391c75d9a60dfbb40fa1592aeab2d53e`
- Test CSV: `762804f22c8c71dd847fb9f0d085ce221b470a15d59cbb2c1a1bd9a92448caa5`
- Test summary: `b05fd83f0dbd722267c36a3456f59804b29e1440fdda4aa2ccbb1e6df19b5f4e`
- Comparison PNG: `32e8cd3697a9d3f225d6ea04c8608056a2662a2209e4288ac28716eba62766aa`

## Verification

- `py_compile`: passed for all three scripts.
- `--help`: passed for all three scripts.
- Frozen split counts: passed, no split regeneration.
- Prediction uniqueness: 1680/1680 unique sample-method keys.
- Test audit: `test_evaluation_count=1`, 480 predictions.
- Filter-input leakage flags: all false.
- Missing values: never converted to zero. No-processing short-missing has formal RMSE/max/derivative metrics null and coverage below 1; the separate penalty is explicit.
- Plot: PNG validation passed.
- Config/B2/raw hashes: unchanged after run.

## Errors and corrections

- Initial Matplotlib import warned that `/home/a531/.config/matplotlib` was not writable. Commands were rerun with `MPLCONFIGDIR=/tmp/humanvla_matplotlib`; no result data were affected.
- Post-run report audit found that partial no-processing outputs could produce misleading max and derivative metrics from surviving clean points. The evaluator was corrected to emit null/status `not_available_missing_output`; reports were regenerated from the same immutable prediction file. Filters, selected parameters and the single test run were not rerun or changed.
- No algorithm execution failure occurred.

## Limitations and next step

- One episode, 8-frame windows and phase distributions that differ by split limit external validity.
- Test includes only retract and idle source windows.
- Synthetic confidence is inherited from clean OpenPose output, so it is not guaranteed to correlate with injected corruption.
- Phase-boundary shift cannot be estimated from same-phase windows.
- Status: complete pending independent/Claude review. Stop here; do not begin T07C-B4.
