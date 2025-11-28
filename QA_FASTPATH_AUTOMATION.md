QA Fast-Path Automation
=======================

What it does
------------
- Gates → QE pre-rank → E8 rerank to prune heavy work early.
- Rust batch kernels accelerate invariants and E8 scoring.
- Evaluation runs automatically each agent loop and during `make metrics`.

Where results live
------------------
- `artifacts/evals/fastpath_eval.json/.txt`: pipeline vs baseline, speedups
- `artifacts/evals/daily_summary_latest.txt`: human-readable daily summary
- `artifacts/evals/fastpath_trends.json/.png`: speedup trend snapshots/plot

Useful environment toggles
--------------------------
- Gate policy
  - `QA_FP_ENABLE_WHEEL=1` (default): wheel gate on d,a residues (1,5,7,11)
  - `QA_FP_ENABLE_FAMILY=1` (default): family gate via golden-ratio closeness
  - `QA_FP_FAMILY_TOL=0.05`: tolerance for a/d and e/b gates
  - `QA_FP_POS_MIN=0.0`: positivity min for (b,e,d,a)
- QE feature weights
  - `QA_QE_CURV_WEIGHT=0.25`: curvature proxy weight (Y/Z and C/F)
  - `QA_QE_FAMILY_WEIGHT=0.25`: family score weight
  - `QA_QE_PHI_WEIGHT` / `QA_QE_PHI_EB_WEIGHT`: direct φ closeness weights
  - `QA_QE_IDEAL_WEIGHT`: quick E8 ideal root cosine weight
- E8 strategy
  - `QA_E8_PREFER_NUMPY=1`: force NumPy BLAS path
  - `QA_E8_DISABLE_RUST=1`: disable Rust path
  - `QA_E8_VEC_CHUNK` / `QA_E8_ROOT_CHUNK`: chunk sizes

- Quick ideal E8 gate
  - `ideal_min` (fast_prune_and_rank arg) to require quick ideal ≥ threshold.

Developer utilities
-------------------
- `make fast-eval`: one-button fast-path evaluation
- `make fast-prune-stream`: streaming prune for huge N
- `make prepare-e8-roots` or `python qa_lab/scripts/generate_e8_roots.py`: ensure 240 E8 roots

Notes
-----
- Mod-9 closure gate is implemented but off by default; enable when inputs are integer-like.
- Defaults aim for stable speedups without hurting recall; adjust env toggles to explore.
