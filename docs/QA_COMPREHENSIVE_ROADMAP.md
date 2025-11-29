# QA Lab: Comprehensive Research & Experiment Roadmap

**Version:** 2.0 (Ingestion-Integrated)
**Date:** 2025-11-26
**Status:** Planning Phase

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current Baseline](#current-baseline)
3. [Ingestion-Driven Experiments](#ingestion-driven-experiments) ⭐ NEW
4. [Robustness & Reproducibility](#robustness-reproducibility)
5. [Mechanistic Ablations](#mechanistic-ablations)
6. [Real-World Datasets](#real-world-datasets)
7. [Advanced Architectures](#advanced-architectures)
8. [Compute & Memory Profiling](#compute-memory-profiling)
9. [Accuracy & Generalization](#accuracy-generalization)
10. [Theoretical Foundations](#theoretical-foundations) ⭐ NEW
11. [Priority Matrix & Timeline](#priority-matrix-timeline)

---

## Executive Summary

This roadmap consolidates:
- **Experimental sweeps** to validate HGD robustness across parameters, datasets, and architectures
- **Ingestion-driven research** from 22 papers in `ingestion_candidates/` folder
- **Theoretical foundations** (sheaf cohomology, quantum memory, statistical mechanics)
- **Real-world applications** (ARC-AGI, HSI, quantum systems)

**Key Integration Points:**
- 11/22 ingestion papers already processed → ready for implementation
- 4 high-priority theoretical frameworks identified
- 15+ new experiment proposals derived from ingestion papers

---

## Current Baseline

### ✅ Working (As of 2025-11-26)

**Synthetic Benchmarks:**
- `qa_speed_benchmark.rs`: Canonical HGD vs SGD on convex quadratic loss
- **Results:** step_speedup = 2.09×, compute_ratio = 1.25×
- **Guardrails:** Hard thresholds ≥1.2× enforced in `qa_paper.py`

**Raman Classification:**
- `qa_raman_demo.rs`: 12-class spectral classifier (bacteria identification)
- **Features:** Grid features + QA tuples (default: `--feat-mode grid+qa`)
- **Optimizer:** SGD vs HGD comparison
- **Output:** CSV logs, accuracy curves, LaTeX section

**PCN/JEPA Demos:**
- `qa_pcn_sheaf_demo.rs`: Predictive coding network with sheaf geometry
- `qa_jepa_demo.rs`: Joint-Embedding Predictive Architecture
- **Status:** Convergence curves plotted; not yet in JSON tracking

**LaTeX Pipeline:**
- `make qa-paper` → Generates Overleaf bundle with 4 figures + 2 LaTeX sections
- **Artifacts:** `artifacts/overleaf/` (ready for submission)
- **JSON Receipt:** `artifacts/overleaf/qa_paper.json`

---

## Ingestion-Driven Experiments ⭐ NEW

*Experiments derived from `ingestion_candidates/` research papers*

### 3.1 QA-JEPA Production Integration
**Source:** `qa_jepa.odt` (✅ Processed)
**Status:** Code exists (`qa_jepa_encoder.py`), not integrated into `qa-paper`
**Priority:** HIGH

**Description:** 12 JEPA variants (I-JEPA, V-JEPA, TS-JEPA, etc.) using QA tuples as latent embeddings.

**Implementation:**
- **Bin:** `src/bin/qa_jepa_mnist.rs` (extend existing `qa_jepa_demo.rs`)
- **Task:** MNIST patch prediction (28×28 → 14×14 patches)
- **Metrics:**
  - Reconstruction loss (MSE)
  - Latent space alignment (E8 metric)
  - Training speed (HGD vs SGD)
- **Artifacts:**
  - CSV: `target/qa_jepa/jepa_mnist_{opt}.csv`
  - Plot: `plots/qa_jepa_mnist_reconstruction.png`
  - LaTeX: `docs/qa_jepa_section.tex`
- **JSON Metrics:**
  ```json
  "jepa_mnist": {
    "sgd_reconstruction_mse": 0.042,
    "hgd_reconstruction_mse": 0.018,
    "e8_alignment_improvement": 0.15,
    "epochs_to_convergence": {"sgd": 45, "hgd": 28}
  }
  ```

**Makefile Target:** `make qa-runs-jepa-mnist`

**Impact:** ⭐⭐⭐⭐⭐ World model for predictive learning; validates QA as latent space

---

### 3.2 QA-ARC Vision Hybrid
**Source:** `arc_is_a_vision_problem.odt` (✅ Processed)
**Status:** Architecture designed, implementation pending
**Priority:** HIGH (AGI Benchmark)

**Description:** Dual-branch architecture combining Vision Transformer + QA-JEPA algebraic reasoning for ARC-AGI benchmark.

**Implementation:**
- **Bin:** `src/bin/qa_arc_hybrid.rs`
- **Architecture:**
  - **Branch 1:** ViT (grid pixels → visual embeddings)
  - **Branch 2:** QA encoder (grid → QA tuples → E8 alignment)
  - **Fusion:** Concatenate embeddings → MLP classifier
- **Dataset:** ARC-AGI-1 public evaluation set (400 tasks)
- **Baseline:** Pure ViT achieves 54.5% (MIT paper)
- **Target:** 60-65% with QA hybrid
- **Artifacts:**
  - CSV: `target/qa_arc/arc_hybrid_scores.csv`
  - Plot: `plots/qa_arc_hybrid_performance.png`
  - LaTeX: `docs/qa_arc_section.tex`
- **JSON Metrics:**
  ```json
  "arc_hybrid": {
    "baseline_vit_accuracy": 0.545,
    "qa_hybrid_accuracy": 0.625,
    "improvement": 0.080,
    "tasks_solved": {"baseline": 218, "hybrid": 250}
  }
  ```

**Makefile Target:** `make qa-runs-arc-hybrid`

**Impact:** ⭐⭐⭐⭐⭐ Major AGI benchmark; publishable result if >60% achieved

---

### 3.3 Quantum Memory Encoding
**Source:** `ramen_quantum_memory.odt`
**Status:** Not processed
**Priority:** MEDIUM

**Description:** Map RAMEN quantum memory architecture to QA tuples; test if QA mod-24 structure mirrors quantum state superposition.

**Implementation:**
- **Bin:** `src/bin/qa_quantum_memory.rs`
- **Task:** Encode quantum states as QA tuples; measure fidelity under noise
- **Metrics:**
  - State fidelity (F = |⟨ψ|φ⟩|²)
  - Decoherence resistance
  - E8 alignment of quantum gates
- **Artifacts:**
  - CSV: `target/qa_quantum/quantum_fidelity.csv`
  - Plot: `plots/qa_quantum_decoherence.png`
- **JSON Metrics:**
  ```json
  "quantum_memory": {
    "fidelity_mean": 0.92,
    "decoherence_time_improvement": 1.35,
    "e8_gate_alignment": 0.78
  }
  ```

**Makefile Target:** `make qa-runs-quantum-memory`

**Impact:** ⭐⭐⭐⭐ Novel quantum computing application

---

### 3.4 Statistical Mechanics Framework
**Source:** `statistical_mechanics_for_real_brains.odt`, `statistical_mechanics.odt`
**Status:** Not processed
**Priority:** MEDIUM (Theoretical Foundation)

**Description:** Apply statistical mechanics to QA dynamics; derive thermodynamic potentials (entropy, free energy) for QA state transitions.

**Implementation:**
- **Bin:** `src/bin/qa_stat_mech.rs`
- **Metrics:**
  - Partition function Z(β) for QA tuples
  - Entropy S = -∑ p log p (state distribution)
  - Free energy F = -kT log Z
  - Temperature analog (β = 1/learning_rate?)
- **Task:** Derive closed-form expressions for QA thermodynamics
- **Artifacts:**
  - LaTeX: `docs/qa_stat_mech_derivations.tex`
  - Plot: `plots/qa_entropy_vs_training.png`
- **JSON Metrics:**
  ```json
  "stat_mech": {
    "entropy_initial": 3.45,
    "entropy_final": 1.12,
    "free_energy_reduction": 2.33,
    "temperature_analog_optimal": 0.05
  }
  ```

**Makefile Target:** `make qa-theory-stat-mech`

**Impact:** ⭐⭐⭐⭐ Rigorous theoretical foundation for HGD optimization

---

### 3.5 Sheaf Cohomology Extension
**Source:** `sheafcohomologyUntitled 1.odt` (NEW!)
**Status:** Not processed
**Priority:** HIGH (Theoretical Foundation)

**Description:** Formalize PCN sheaf geometry using sheaf cohomology; prove global-local consistency properties.

**Implementation:**
- **Theory:** Derive cohomology groups H¹(X, F) for QA sheaf F on graph X
- **Bin:** `src/bin/qa_sheaf_cohomology.rs`
- **Task:** Compute Čech cohomology for PCN with conflicting local predictions
- **Metrics:**
  - Dimension of H¹ (measures inconsistency)
  - Sheaf Laplacian spectrum
  - Global section existence (H⁰ ≠ ∅ → consistent global prediction)
- **Artifacts:**
  - LaTeX: `docs/qa_sheaf_cohomology_proof.tex`
  - Plot: `plots/qa_sheaf_spectrum.png`
- **JSON Metrics:**
  ```json
  "sheaf_cohomology": {
    "h0_dimension": 1,
    "h1_dimension": 0,
    "global_consistency": true,
    "laplacian_spectral_gap": 0.45
  }
  ```

**Makefile Target:** `make qa-theory-sheaf-cohomology`

**Impact:** ⭐⭐⭐⭐⭐ Rigorous mathematical foundation for PCN; publishable in pure math journals

---

### 3.6 Entangled Schrödinger Bridge
**Source:** `entangled_schrodinger_bridge_mapping.odt` (34 MB PDF)
**Status:** Not processed
**Priority:** LOW (Exploratory)

**Description:** Map Schrödinger bridge optimal transport to QA state transitions; test if HGD follows optimal transport geodesics.

**Implementation:**
- **Theory:** Schrödinger bridge interpolates between distributions via KL-minimizing path
- **Hypothesis:** HGD trajectories approximate Schrödinger bridge in QA tuple space
- **Metrics:**
  - KL divergence along HGD path
  - Comparison to analytic Schrödinger solution
- **Artifacts:**
  - LaTeX: `docs/qa_schrodinger_bridge.tex`
  - Plot: `plots/qa_hgd_geodesic.png`

**Makefile Target:** `make qa-theory-schrodinger`

**Impact:** ⭐⭐⭐ Theoretical insight into HGD optimality

---

### 3.7 AI Co-Scientist Integration
**Source:** `ai_coscientist.odt`, `alpharesearch_ai_scientist.odt`
**Status:** Not processed
**Priority:** LOW (Meta-Research)

**Description:** Automate experiment design using QA system as meta-learner; generate new hypotheses from E8 alignment patterns.

**Implementation:**
- **Bin:** Extend `qa_agents/cli/` with autonomous experiment generator
- **Task:** Input = QA tuple dataset; Output = ranked list of experiment proposals
- **Metrics:**
  - Novelty score (distance from existing experiments in E8 space)
  - Feasibility score (compute budget estimate)
  - Impact score (predicted publication tier)

**Makefile Target:** `make qa-meta-coscientist`

**Impact:** ⭐⭐⭐⭐ Autonomous research acceleration

---

## Robustness & Reproducibility

### 4.1 Expanded Parameter Grid
**Priority:** HIGH
**Implementation:** Extend `qa_speed_benchmark.rs` to accept config files
**Params:** dims=[4,8,16,32,64], lr_sgd=[0.05,0.1,0.2], repeats=5
**Artifacts:** CSV + heatmap plot + LaTeX
**JSON Metrics:**
```json
"sweep_grid": {
  "total_configs": 15,
  "wins": 14,
  "win_rate": 0.93,
  "mean_speedup": 2.1,
  "speedup_std": 0.15
}
```
**Makefile Target:** `make qa-runs-sweep-grid`

---

### 4.2 Batch Size Impact
**Priority:** MEDIUM
**Implementation:** Add `--batch-size` flag to `qa_raman_demo.rs`
**Params:** batch_sizes=[16,32,64,128]
**Artifacts:** CSV + plot
**JSON Metrics:**
```json
"batch_size_sweep": {
  "batch_sizes": [16, 32, 64, 128],
  "hgd_speedup_by_batch": [2.0, 2.1, 1.9, 1.8],
  "optimal_batch": 32
}
```
**Makefile Target:** `make qa-runs-batch-sweep`

---

### 4.3 Noise Robustness
**Priority:** MEDIUM
**Implementation:** Add noise injection to `qa_raman_demo.rs`
**Params:** noise_types=["gaussian","poisson"], noise_levels=[0.0,0.05,0.1,0.2]
**Artifacts:** CSV + degradation plot
**JSON Metrics:**
```json
"noise_robustness": {
  "gaussian_degradation": {"0.0": 0.92, "0.1": 0.88, "0.2": 0.82},
  "hgd_advantage_preserved": true
}
```
**Makefile Target:** `make qa-runs-noise-sweep`

---

### 4.4 Seed Stability (10 seeds)
**Priority:** HIGH
**Implementation:** Modify `qa_speed_benchmark.rs` to run `--seeds 10`
**Artifacts:** CSV + error bar plot
**JSON Metrics:**
```json
"seed_stability": {
  "seeds": 10,
  "speedup_mean": 2.08,
  "speedup_std": 0.12,
  "speedup_ci_95": [1.95, 2.21]
}
```
**Makefile Target:** `make qa-runs-seed-stability`

---

## Mechanistic Ablations

### 5.1 Component Masking
**Priority:** HIGH
**Implementation:** Add `--ablate` flag to `qa_speed_benchmark.rs`
**Ablations:** none, mod24-only, mod9-only, no-modular
**Artifacts:** CSV + component contribution plot
**JSON Metrics:**
```json
"component_ablation": {
  "mod24_contribution": 0.6,
  "mod9_contribution": 0.4,
  "synergy_gain": 0.08
}
```
**Makefile Target:** `make qa-runs-ablate-components`

---

### 5.2 LR Coupling Analysis
**Priority:** MEDIUM
**Implementation:** Sweep `--lrh-mult` in `qa_paper.py --sweep`
**Params:** lrh_mults=[1.5,2.0,2.5]
**Artifacts:** CSV + LR coupling plot
**JSON Metrics:**
```json
"lr_coupling": {
  "optimal_multiplier": 2.0,
  "speedup_by_mult": {"1.5": 1.8, "2.0": 2.1, "2.5": 1.9}
}
```
**Makefile Target:** `make qa-runs-lr-coupling`

---

### 5.3 Raman Feature Ablation ⭐ USER HIGHLIGHTED
**Priority:** HIGH
**Implementation:** Sweep `--feat-mode` {grid, qa, grid+qa} × {SGD, HGD}
**Artifacts:** CSV + feature comparison plot
**JSON Metrics:**
```json
"raman_feature_ablation": {
  "grid_only": {"sgd_acc": 0.88, "hgd_acc": 0.90},
  "qa_only": {"sgd_acc": 0.75, "hgd_acc": 0.78},
  "grid+qa": {"sgd_acc": 0.92, "hgd_acc": 0.94},
  "best_mode": "grid+qa"
}
```
**Makefile Target:** `make qa-runs-raman-ablation`

---

### 5.4 Optimizer Comparison
**Priority:** MEDIUM
**Implementation:** Add `--opt` {sgd,adam,adamw,lion,8bit}
**Fair Comparison:** Per-optimizer LR grid search
**Artifacts:** CSV + optimizer ranking plot
**JSON Metrics:**
```json
"optimizer_comparison": {
  "sgd_best": {"steps": 232, "lr": 0.2},
  "adam_best": {"steps": 198, "lr": 0.01},
  "hgd_best": {"steps": 111, "lr": 0.4},
  "hgd_rank": 1
}
```
**Makefile Target:** `make qa-runs-optimizer-sweep`

---

## Real-World Datasets

### 6.1 HSI Classification ⭐ USER HIGHLIGHTED
**Priority:** HIGH
**Status:** Data available (`multimodal_data/HSI_Tr.mat`)
**Implementation:** Create `src/bin/qa_hsi_demo.rs`
**Dataset:** 16-class hyperspectral imaging
**Features:** Spectral bands → QA tuples + grid
**Artifacts:** CSV + accuracy curves + LaTeX
**JSON Metrics:**
```json
"hsi_classification": {
  "dataset": "HSI_Tr",
  "classes": 16,
  "sgd_best_acc": 0.87,
  "hgd_best_acc": 0.91,
  "epochs_to_85pct": {"sgd": 45, "hgd": 28}
}
```
**Makefile Target:** `make qa-runs-hsi`

---

### 6.2 Tabular UCI Datasets
**Priority:** LOW
**Implementation:** `src/bin/qa_uci_demo.rs`
**Datasets:** Wine, Breast Cancer, Iris
**Artifacts:** CSV + comparison plot
**JSON Metrics:**
```json
"uci_datasets": {
  "wine": {"sgd_acc": 0.96, "hgd_acc": 0.98},
  "iris": {"sgd_acc": 0.97, "hgd_acc": 0.99}
}
```
**Makefile Target:** `make qa-runs-uci`

---

### 6.3 Time-Series (ECG/Synthetic)
**Priority:** MEDIUM
**Implementation:** Extend `qa_pcn_sheaf_demo.rs`
**Task:** Multi-step prediction; measure divergence
**Artifacts:** CSV + stability plot
**JSON Metrics:**
```json
"timeseries": {
  "divergence_rate_sgd": 0.12,
  "divergence_rate_hgd": 0.04,
  "stability_gain": 3.0
}
```
**Makefile Target:** `make qa-runs-timeseries`

---

## Advanced Architectures

### 7.1 QA-Fourier Layer
**Priority:** MEDIUM
**Implementation:** `src/bin/qa_fourier_layer_demo.rs`
**Task:** Toy sequence modeling (copy task)
**Metrics:** Ops/time vs naive attention
**Artifacts:** CSV + ops-time plot
**JSON Metrics:**
```json
"qa_fourier": {
  "ops_reduction": 0.35,
  "time_speedup": 1.4,
  "accuracy_preserved": true
}
```
**Makefile Target:** `make qa-runs-fourier`

---

### 7.2 PCN Recurrent (Long Horizon)
**Priority:** LOW
**Implementation:** Modify `qa_pcn_sheaf_demo.rs` with `--horizon` flag
**Task:** Extended prediction horizons
**Artifacts:** CSV + horizon stability plot
**Makefile Target:** `make qa-runs-pcn-horizon`

---

## Compute & Memory Profiling

### 8.1 CPU Wall-Clock & Op Proxies
**Priority:** HIGH
**Implementation:** Add `--profile` flag to all demos
**Metrics:** Time per epoch, op counts, memory footprint
**Artifacts:** CSV + time-ops plot
**JSON Metrics:**
```json
"profiling": {
  "raman_sgd_time_per_epoch": 1.2,
  "raman_hgd_time_per_epoch": 1.4,
  "time_overhead": 1.17,
  "memory_bytes_per_sample": 512
}
```
**Makefile Target:** `make qa-runs-profile`

---

### 8.2 SIMD/Parallel Toggles
**Priority:** LOW
**Implementation:** Compare `cargo build --features rayon` vs default
**Artifacts:** CSV + throughput comparison
**Makefile Target:** `make qa-runs-simd-compare`

---

## Accuracy & Generalization

### 9.1 Train/Val Split with Early Stopping
**Priority:** HIGH
**Implementation:** Add `--val-split 0.2`, `--early-stop-patience 10`
**Artifacts:** CSV + train/val curves
**JSON Metrics:**
```json
"generalization": {
  "train_acc": 0.96,
  "val_acc": 0.92,
  "generalization_gap": 0.04,
  "early_stopped_epoch": 38
}
```
**Makefile Target:** `make qa-runs-generalization`

---

### 9.2 Class Imbalance Robustness
**Priority:** MEDIUM
**Implementation:** Add `--class-weights` flag; generate confusion matrices
**Artifacts:** CSV + confusion matrix plot
**Makefile Target:** `make qa-runs-imbalance`

---

## Theoretical Foundations ⭐ NEW

### 10.1 Volk-Grant Toroidal Geometry Refinement
**Source:** `Toroids, Vortices, Knots, Topology and Quanta, Part 2.doc` (✅ Processed)
**Priority:** MEDIUM
**Status:** Conceptual implementation exists (`qa_toroid_sumproduct.py`); geometric framework pending

**Task:** Implement full bipolar coordinate system from Volk's paper
**Artifacts:**
- LaTeX: `docs/qa_volk_geometry_complete.tex`
- Plot: `plots/qa_bipolar_coordinates.png`
**Makefile Target:** `make qa-theory-volk-geometry`

---

### 10.2 Sum-Product Conjecture Validation
**Source:** `sum_product_conjecture.pdf` (✅ Processed)
**Priority:** LOW (Already validated by Gemini)
**Status:** Implementation confirmed correct; no further action needed

---

### 10.3 JIT Compilation for QA
**Source:** `qa_jit.odt` (NEW!)
**Priority:** MEDIUM
**Status:** Not processed

**Description:** Just-in-time compilation for QA tuple operations; potential for 10-100× speedup.

**Implementation:**
- Parse `qa_jit.odt` to extract JIT strategy
- Prototype using LLVM-IR or cranelift
- Benchmark against interpreted Rust
**Makefile Target:** `make qa-jit-benchmark`

---

## Priority Matrix & Timeline

### Tier 1: IMMEDIATE (1-2 weeks)
| Experiment | Effort | Impact | Ingestion Source |
|------------|--------|--------|------------------|
| Raman Feature Ablation | 1 day | ⭐⭐⭐⭐ | User request |
| Seed Stability (10 seeds) | 1 day | ⭐⭐⭐⭐ | Reproducibility |
| Component Ablation | 2 days | ⭐⭐⭐⭐⭐ | Mechanistic |
| JSON Schema Expansion | 1 day | ⭐⭐⭐⭐ | Infrastructure |
| **JEPA-MNIST Integration** | 3 days | ⭐⭐⭐⭐⭐ | `qa_jepa.odt` |
| **Sheaf Cohomology Formalization** | 3 days | ⭐⭐⭐⭐⭐ | `sheafcohomologyUntitled 1.odt` |

**Total:** ~11 days

---

### Tier 2: SHORT-TERM (3-4 weeks)
| Experiment | Effort | Impact | Ingestion Source |
|------------|--------|--------|------------------|
| HSI Classification | 3 days | ⭐⭐⭐⭐⭐ | User request |
| Parameter Grid Sweep | 2 days | ⭐⭐⭐⭐ | Robustness |
| Batch Size Impact | 1 day | ⭐⭐⭐ | Robustness |
| Train/Val Split | 2 days | ⭐⭐⭐⭐ | Generalization |
| **QA-ARC Hybrid** | 5 days | ⭐⭐⭐⭐⭐ | `arc_is_a_vision_problem.odt` |
| **Statistical Mechanics Framework** | 4 days | ⭐⭐⭐⭐ | `statistical_mechanics*.odt` |

**Total:** ~17 days

---

### Tier 3: MEDIUM-TERM (1-2 months)
| Experiment | Effort | Impact | Ingestion Source |
|------------|--------|--------|------------------|
| Quantum Memory Encoding | 4 days | ⭐⭐⭐⭐ | `ramen_quantum_memory.odt` |
| Noise Robustness | 2 days | ⭐⭐⭐ | Robustness |
| LR Coupling | 2 days | ⭐⭐⭐ | Ablation |
| QA-Fourier Layer | 5 days | ⭐⭐⭐⭐ | Architecture |
| Optimizer Comparison | 3 days | ⭐⭐⭐ | Ablation |
| **QA-JIT Compilation** | 7 days | ⭐⭐⭐⭐ | `qa_jit.odt` |

**Total:** ~23 days

---

### Tier 4: LONG-TERM (3+ months)
| Experiment | Effort | Impact | Ingestion Source |
|------------|--------|--------|------------------|
| UCI Datasets | 2 days | ⭐⭐ | Real data |
| Time-Series | 3 days | ⭐⭐⭐ | Real data |
| PCN Horizon | 2 days | ⭐⭐ | Architecture |
| SIMD Comparison | 2 days | ⭐⭐ | Profiling |
| Schrödinger Bridge | 5 days | ⭐⭐⭐ | `entangled_schrodinger_bridge_mapping.odt` |
| AI Co-Scientist | 10 days | ⭐⭐⭐⭐ | `ai_coscientist.odt` |

**Total:** ~24 days

---

## Integration Workflow (Per Experiment)

1. **Process Ingestion Paper** (if applicable)
   - Extract .odt/.pdf: `unzip -p file.odt content.xml | xmllint --format -`
   - Analyze with Gemini/Claude: Store in `qa_lab/{PAPER}_ANALYSIS.md`

2. **Create Rust Bin**
   - `src/bin/qa_{experiment}_demo.rs`
   - CSV logging to `target/qa_{category}/{experiment}.csv`

3. **Add Plot Script**
   - `scripts/qa_plot_{experiment}.py`
   - Save to `plots/qa_{experiment}.png`

4. **Update LaTeX Template**
   - Add subsection to `docs/templates/qa_{experiment}_section.tex`

5. **Extend qa_paper.py**
   - Add CSV parsing + JSON metrics
   - Update `gather()` function

6. **Add Makefile Targets**
   - `qa-runs-{experiment}`: Run demo and save CSV
   - `qa-plots-{experiment}`: Generate plots
   - Include in `qa-paper` if mature

7. **Update Guardrails**
   - Add soft/hard thresholds to `qa_paper.py` if needed

8. **Document**
   - Update this roadmap with ✅ status
   - Commit to git with `[experiment] {short description}`

---

## JSON Schema (Extended)

```json
{
  "canonical": {
    "step_speedup": 2.08,
    "compute_ratio": 1.25
  },
  "sweeps": {
    "grid": {"wins": 14, "total": 15, "mean_speedup": 2.1},
    "batch": {"optimal_batch": 32, "speedup_by_batch": [...]},
    "noise": {"hgd_advantage_preserved": true}
  },
  "ablations": {
    "components": {"mod24_contribution": 0.6, "mod9_contribution": 0.4},
    "features": {"best_mode": "grid+qa"},
    "lr_coupling": {"optimal_multiplier": 2.0}
  },
  "datasets": {
    "raman": {"sgd_best_acc": 0.92, "hgd_best_acc": 0.94},
    "hsi": {"sgd_best_acc": 0.87, "hgd_best_acc": 0.91},
    "arc": {"baseline_vit": 0.545, "qa_hybrid": 0.625}
  },
  "architectures": {
    "jepa_mnist": {"sgd_mse": 0.042, "hgd_mse": 0.018},
    "fourier": {"ops_reduction": 0.35, "time_speedup": 1.4}
  },
  "theory": {
    "sheaf_cohomology": {"global_consistency": true, "h1_dimension": 0},
    "stat_mech": {"entropy_reduction": 2.33},
    "quantum_memory": {"fidelity_mean": 0.92}
  },
  "profiling": {
    "time_overhead": 1.17,
    "memory_bytes_per_sample": 512
  },
  "generalization": {
    "train_acc": 0.96,
    "val_acc": 0.92,
    "generalization_gap": 0.04
  }
}
```

---

## Guardrails Policy

### Hard Thresholds (Fail CI)
- **Canonical synthetic:** `step_speedup ≥ 1.2`, `compute_ratio ≥ 1.2`

### Soft Warnings (Log only)
- **Raman/HSI:** HGD should reach target accuracy faster than SGD
- **JEPA/ARC:** HGD reconstruction/accuracy should exceed SGD

### No Guardrails (Exploratory)
- All ablations, theory papers, quantum experiments

---

## Next Actions for Claude

1. **Immediate:**
   - ✅ Map ingestion papers to experiments (DONE)
   - Implement Raman feature ablation sweep
   - Process `sheafcohomologyUntitled 1.odt` → derive H¹ metrics

2. **Short-term:**
   - Process `qa_jit.odt` → prototype JIT benchmark
   - Integrate JEPA-MNIST into `qa-paper` pipeline
   - Expand JSON schema with theory + ingestion metrics

3. **Medium-term:**
   - QA-ARC hybrid implementation (AGI benchmark target)
   - HSI classification demo
   - Statistical mechanics formal derivations

---

## Ingestion Paper Status Tracker

| Paper | Size | Status | Priority | Experiment Derived | Impact |
|-------|------|--------|----------|-------------------|--------|
| qa_jepa.odt | 48 KB | ✅ Processed | HIGH | JEPA-MNIST | ⭐⭐⭐⭐⭐ |
| arc_is_a_vision_problem.odt | 78 KB | ✅ Processed | HIGH | QA-ARC Hybrid | ⭐⭐⭐⭐⭐ |
| sheafcohomologyUntitled 1.odt | 59 KB | ⏳ New | HIGH | Sheaf Cohomology | ⭐⭐⭐⭐⭐ |
| qa_jit.odt | 64 KB | ⏳ New | MEDIUM | JIT Compilation | ⭐⭐⭐⭐ |
| ramen_quantum_memory.odt | 64 KB | ⏳ Pending | MEDIUM | Quantum Memory | ⭐⭐⭐⭐ |
| statistical_mechanics*.odt | 114 KB | ⏳ Pending | MEDIUM | Stat Mech Framework | ⭐⭐⭐⭐ |
| entangled_schrodinger*.odt | 34 MB | ⏳ Pending | LOW | Schrödinger Bridge | ⭐⭐⭐ |
| ai_coscientist.odt | 43 KB | ⏳ Pending | LOW | AI Co-Scientist | ⭐⭐⭐⭐ |
| volk_grant_qa.odt | 51 KB | ✅ Processed | DONE | Sum-Product (done) | ⭐⭐⭐⭐⭐ |
| Toroids...Part 2.doc | 909 KB | ✅ Processed | DONE | Volk Geometry | ⭐⭐⭐⭐⭐ |
| sum_product_conjecture.pdf | 1.2 MB | ✅ Processed | DONE | Validated | ⭐⭐⭐⭐⭐ |

**Total Processed:** 11/22 (50%)
**High Priority Remaining:** 3 (sheaf cohomology, qa_jit, ramen)

---

## Success Metrics (3-Month Checkpoint)

### Evidence Bundle Completeness
- [ ] ≥20 experiments in JSON receipt
- [ ] ≥10 figures in Overleaf bundle
- [ ] ≥5 LaTeX sections ready for submission
- [ ] ≥3 ingestion papers integrated into experiments

### Publication Readiness
- [ ] ARC-AGI result >60% (publishable at top-tier venue)
- [ ] HSI classification competitive with state-of-art
- [ ] Sheaf cohomology proof formalized (pure math journal)
- [ ] Statistical mechanics derivations complete (physics journal)

### Robustness Validation
- [ ] HGD wins ≥80% of parameter grid (seed stability)
- [ ] HGD advantage preserved under noise/imbalance
- [ ] Generalization gap <5% on all real datasets

---

**END OF ROADMAP**
