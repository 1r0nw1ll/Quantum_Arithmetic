# QA Paper Artifacts

This directory collects auto-generated evidence that Quantum Arithmetic (QA) reduces
training time and compute compared to classical SGD-style optimization.

## Files

- `qa_training_compute_section.tex`
  LaTeX snippet describing the benchmark setup and reporting QA vs SGD metrics
  (steps-to-tolerance and a compute proxy). Include it via:

  ```tex
  % In your main .tex
  \input{qa_training_compute_section.tex}
  ```

- `qa_benchmarks.png`
  Optimization speed comparison between SGD and Harmonic Gradient Descent (HGD):
  steps-to-tolerance and compute proxy.

- `qa_pcn_theta_compare.png`
  PCN sheaf / monodromy comparison for θ = 0 vs θ = π: energy vs step (optionally
  includes Laplacian bounds).

- `qa_jepa_convergence.png`
  JEPA-like toy model convergence: average energy per epoch for SGD vs HGD.

- `qa_overleaf_bundle.tar.gz`
  Tarball for upload to Overleaf or paper repos (mirrors this directory).

## JSON Summary

- `qa_paper.json` (created by `qa_agents/cli/qa_paper.py`)
  Machine-readable summary including artifact list and benchmark metrics
  (e.g., `step_speedup`, `compute_ratio`). Agents can use this to validate
  expected QA speedups and attach evidence to PRs or experiment logs.

## Suggested Text Hooks

- “Figure X compares steps-to-tolerance and proxy compute between SGD and HGD on
  harmonic surfaces; HGD converges in fewer steps and lower effective compute.”
- “Figure Y shows QA-PCN energy behavior under θ = 0 vs θ = π, illustrating stable
  phase-locked dynamics under harmonic guidance.”
- “Figure Z demonstrates smoother and faster convergence for a QA-JEPA toy model
  trained with HGD relative to SGD.”

