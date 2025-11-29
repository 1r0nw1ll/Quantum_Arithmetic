# QA Lab: Immediate Next Steps (Top 5 Priorities)

**Date:** 2025-11-26
**For:** Claude Code / Research Team
**Context:** Comprehensive roadmap created; these are the highest-impact, shortest-path experiments

---

## Priority 1: Raman Feature Ablation (1 day)
**Status:** Partially implemented (code exists, needs full sweep + JSON tracking)
**User Highlight:** Explicitly requested
**Impact:** ⭐⭐⭐⭐ Validates QA tuple contribution to real classification task

### Implementation Plan
1. **Run 6 experiments:** 3 feature modes × 2 optimizers
   ```bash
   # Grid features only
   cargo run --release --bin qa_raman_demo -- --feat-mode grid --opt sgd --log-csv target/qa_raman/raman_grid_sgd.csv
   cargo run --release --bin qa_raman_demo -- --feat-mode grid --opt hgd --log-csv target/qa_raman/raman_grid_hgd.csv

   # QA features only
   cargo run --release --bin qa_raman_demo -- --feat-mode qa --opt sgd --log-csv target/qa_raman/raman_qa_sgd.csv
   cargo run --release --bin qa_raman_demo -- --feat-mode qa --opt hgd --log-csv target/qa_raman/raman_qa_hgd.csv

   # Grid + QA (current default)
   cargo run --release --bin qa_raman_demo -- --feat-mode grid+qa --opt sgd --log-csv target/qa_raman/raman_gridqa_sgd.csv
   cargo run --release --bin qa_raman_demo -- --feat-mode grid+qa --opt hgd --log-csv target/qa_raman/raman_gridqa_hgd.csv
   ```

2. **Create plot script:** `scripts/qa_plot_raman_ablation.py`
   - 3×2 subplot grid: each row = feature mode, columns = SGD/HGD
   - Save to `plots/qa_raman_feature_ablation.png`

3. **Update qa_paper.py:**
   - Add `raman_feature_ablation` to JSON schema
   - Parse CSVs and compute best accuracy per mode
   - Expected output:
     ```json
     "raman_feature_ablation": {
       "grid_only": {"sgd_acc": 0.88, "hgd_acc": 0.90},
       "qa_only": {"sgd_acc": 0.75, "hgd_acc": 0.78},
       "grid+qa": {"sgd_acc": 0.92, "hgd_acc": 0.94},
       "best_mode": "grid+qa",
       "qa_improvement_over_grid": 0.04
     }
     ```

4. **Add Makefile target:**
   ```makefile
   qa-runs-raman-ablation:
       @echo "🧪 Running Raman feature ablation (grid, qa, grid+qa)..."
       # (6 cargo runs from step 1)

   qa-plots-raman-ablation: qa-runs-raman-ablation
       @mkdir -p plots
       python3 scripts/qa_plot_raman_ablation.py --out plots/qa_raman_feature_ablation.png
   ```

5. **Integrate into qa-paper pipeline:**
   - Add `qa-plots-raman-ablation` to `qa-paper` target dependencies

**Acceptance Criteria:**
- ✅ 6 CSV files generated
- ✅ Ablation plot shows clear QA contribution
- ✅ JSON metrics added to `qa_paper.json`
- ✅ `make qa-paper` includes ablation figure in bundle

---

## Priority 2: Seed Stability (10 seeds) (1 day)
**Status:** Not implemented
**Impact:** ⭐⭐⭐⭐ Essential for reproducibility; required for publication

### Implementation Plan
1. **Modify `qa_speed_benchmark.rs`:**
   - Add `--seeds` flag (default: 1)
   - Loop over seeds 0..N
   - Append all results to same CSV (add `seed` column)

2. **Run canonical config with 10 seeds:**
   ```bash
   cargo run --release --bin qa_speed_benchmark -- \
     --dim 16 --lr 0.2 --lr-hgd 0.4 \
     --tol 1e-10 --max-steps 2000 --repeats 1 \
     --hgd-gain 1.8 --hgd-floor 0.3 \
     --seeds 10
   ```

3. **Update plot script:**
   - `scripts/qa_plot_benchmarks.py` should detect multiple seeds
   - Plot mean ± std error bars
   - Show 95% CI shaded region

4. **Update qa_paper.py:**
   - Compute statistics: mean, std, 95% CI
   - Add to JSON:
     ```json
     "seed_stability": {
       "seeds": 10,
       "speedup_mean": 2.08,
       "speedup_std": 0.12,
       "speedup_ci_95": [1.95, 2.21],
       "all_seeds_above_threshold": true
     }
     ```

5. **Update guardrails:**
   - Hard fail if **any** seed falls below 1.2× speedup
   - Warn if std > 0.2 (high variance)

**Acceptance Criteria:**
- ✅ 10 seeds run successfully
- ✅ Mean speedup ≈ 2.08±0.12
- ✅ All seeds pass 1.2× threshold
- ✅ Error bars visible in plot

---

## Priority 3: Component Ablation (2 days)
**Status:** Not implemented
**Impact:** ⭐⭐⭐⭐⭐ Mechanistic understanding of HGD; critical for explaining "why it works"

### Implementation Plan
1. **Modify HGD implementation in `src/qa_core/hgd.rs`:**
   - Add `AblationMode` enum:
     ```rust
     pub enum AblationMode {
         None,           // Full HGD (mod-24 + mod-9)
         Mod24Only,      // Zero out mod-9 component
         Mod9Only,       // Zero out mod-24 component
         NoModular,      // Disable both (equivalent to SGD)
     }
     ```
   - Modify mask computation to respect ablation mode

2. **Add `--ablate` flag to `qa_speed_benchmark.rs`:**
   ```bash
   cargo run --release --bin qa_speed_benchmark -- \
     --dim 16 --lr 0.2 --lr-hgd 0.4 \
     --ablate mod24-only \
     --log-csv target/qa_ablations/ablate_mod24.csv
   ```

3. **Run 4 ablation experiments:**
   - none (baseline HGD)
   - mod24-only
   - mod9-only
   - no-modular (should match SGD)

4. **Create plot:**
   - Bar chart: speedup per ablation mode
   - Expected: none > mod24-only > mod9-only ≈ no-modular

5. **Update JSON:**
   ```json
   "component_ablation": {
     "none": {"speedup": 2.08},
     "mod24_only": {"speedup": 1.65},
     "mod9_only": {"speedup": 1.43},
     "no_modular": {"speedup": 1.0},
     "mod24_contribution": 0.6,
     "mod9_contribution": 0.4,
     "synergy_gain": 0.08
   }
   ```

**Acceptance Criteria:**
- ✅ 4 ablation modes implemented
- ✅ `no-modular` matches SGD within 5%
- ✅ `none` (full HGD) achieves highest speedup
- ✅ Individual contributions quantified

---

## Priority 4: JEPA-MNIST Integration (3 days)
**Status:** Code exists (`qa_jepa_encoder.py`), needs Rust port + MNIST task
**Impact:** ⭐⭐⭐⭐⭐ World model validation; publishable at ML conference
**Ingestion Source:** `qa_jepa.odt` (already processed)

### Implementation Plan
1. **Port JEPA to Rust:**
   - Create `src/qa_core/jepa.rs` (partial implementation exists)
   - Implement I-JEPA variant (simplest):
     - Encoder: x → z (latent embedding)
     - Predictor: z_context → ẑ_target
     - Loss: MSE(ẑ, z) in latent space

2. **Create MNIST patch loader:**
   - Download MNIST to `data/mnist/`
   - Split 28×28 images into 4× 14×14 patches
   - Context = 3 patches, Target = 1 masked patch

3. **Create `src/bin/qa_jepa_mnist.rs`:**
   - Train encoder + predictor with HGD vs SGD
   - Log: reconstruction MSE, E8 alignment of latent codes
   - CSV: `target/qa_jepa/jepa_mnist_{opt}.csv`

4. **Create plot:**
   - Dual y-axis: MSE (left), E8 alignment (right)
   - Show both SGD and HGD curves
   - Save to `plots/qa_jepa_mnist.png`

5. **Update JSON:**
   ```json
   "jepa_mnist": {
     "sgd_reconstruction_mse": 0.042,
     "hgd_reconstruction_mse": 0.018,
     "e8_alignment_improvement": 0.15,
     "epochs_to_convergence": {"sgd": 45, "hgd": 28}
   }
   ```

6. **Add to qa-paper pipeline:**
   - Makefile target: `make qa-runs-jepa-mnist`
   - Include in `qa-paper` bundle

**Acceptance Criteria:**
- ✅ JEPA trains successfully on MNIST patches
- ✅ HGD reconstruction MSE < SGD by ≥20%
- ✅ E8 alignment metric computed and logged
- ✅ Figure included in Overleaf bundle

---

## Priority 5: Sheaf Cohomology Formalization (3 days)
**Status:** Paper just discovered (`sheafcohomologyUntitled 1.odt`)
**Impact:** ⭐⭐⭐⭐⭐ Rigorous mathematical foundation; publishable in pure math journal
**Ingestion Source:** `sheafcohomologyUntitled 1.odt` (NEW!)

### Implementation Plan
1. **Process ingestion paper:**
   ```bash
   # Extract ODT content
   unzip -p "../ingestion candidates/sheafcohomologyUntitled 1.odt" content.xml | \
     xmllint --format - > /tmp/sheaf_cohomology.xml

   # Convert to readable text
   python3 scripts/odt_to_text.py \
     --in "../ingestion candidates/sheafcohomologyUntitled 1.odt" \
     --out artifacts/ingestion/sheaf_cohomology.txt
   ```

2. **Analyze with Claude/Gemini:**
   - Extract key theorems, definitions, proofs
   - Map to QA-PCN sheaf structure
   - Identify cohomology groups H⁰, H¹ for PCN graph

3. **Implement Čech cohomology computation:**
   - Create `src/qa_core/sheaf_cohomology.rs`
   - Given PCN graph G with QA tuple sheaf F:
     - Compute C⁰ (0-cochains): local predictions at nodes
     - Compute C¹ (1-cochains): differences across edges
     - Boundary map δ⁰: C⁰ → C¹
     - Kernel of δ⁰ = global sections (H⁰)
     - Cokernel = H¹ (measures inconsistency)

4. **Create demo bin:**
   - `src/bin/qa_sheaf_cohomology_demo.rs`
   - Construct PCN with conflicting local predictions
   - Compute dim(H⁰), dim(H¹), sheaf Laplacian spectrum
   - CSV: `target/qa_sheaf/cohomology_metrics.csv`

5. **LaTeX write-up:**
   - Formal definitions: sheaf F, Čech complex, cohomology groups
   - Theorem: "If H¹(G, F) = 0, then global consistent prediction exists"
   - Proof sketch using sheaf Laplacian spectral gap
   - Save to `docs/qa_sheaf_cohomology_proof.tex`

6. **Update JSON:**
   ```json
   "sheaf_cohomology": {
     "h0_dimension": 1,
     "h1_dimension": 0,
     "global_consistency": true,
     "laplacian_spectral_gap": 0.45,
     "theorem_proven": "H1=0 implies global section exists"
   }
   ```

**Acceptance Criteria:**
- ✅ Ingestion paper processed and analyzed
- ✅ Cohomology groups H⁰, H¹ computed for example PCN
- ✅ LaTeX proof formalized (ready for arXiv submission)
- ✅ Sheaf Laplacian spectrum visualized

---

## Execution Order (Week 1 Plan)

**Day 1 (Today):**
- [x] Create comprehensive roadmap (DONE)
- [ ] Start Priority 1: Raman feature ablation
  - Run 6 experiments (2 hours)
  - Create plot script (1 hour)

**Day 2:**
- [ ] Complete Priority 1: Raman ablation
  - Update qa_paper.py (1 hour)
  - Add Makefile targets (30 min)
  - Test full pipeline (30 min)
- [ ] Start Priority 2: Seed stability
  - Modify qa_speed_benchmark.rs (2 hours)
  - Run 10-seed experiment (1 hour)

**Day 3:**
- [ ] Complete Priority 2: Seed stability
  - Update plot script (1 hour)
  - Update JSON schema (30 min)
  - Update guardrails (30 min)
- [ ] Start Priority 3: Component ablation
  - Design AblationMode enum (1 hour)
  - Modify HGD implementation (2 hours)

**Day 4:**
- [ ] Complete Priority 3: Component ablation
  - Add --ablate flag (1 hour)
  - Run 4 ablation experiments (2 hours)
  - Create plot + JSON update (1 hour)
- [ ] Start Priority 5: Sheaf cohomology
  - Process ingestion paper (2 hours)

**Day 5:**
- [ ] Continue Priority 5: Sheaf cohomology
  - Analyze with AI (2 hours)
  - Design cohomology computation (3 hours)

**Days 6-7 (Weekend):**
- [ ] Complete Priority 5: Sheaf cohomology
  - Implement Čech cohomology (4 hours)
  - Create demo bin (2 hours)
  - Write LaTeX proof (3 hours)

**Week 2:**
- [ ] Priority 4: JEPA-MNIST (full 3 days)
- [ ] Additional priorities as time allows

---

## Quick-Start Commands

### Run All Priority 1-3 Experiments (Canonical Configs)
```bash
# Priority 1: Raman ablation (parallel)
make qa-runs-raman-ablation

# Priority 2: Seed stability
cargo run --release --bin qa_speed_benchmark -- \
  --dim 16 --lr 0.2 --lr-hgd 0.4 --seeds 10

# Priority 3: Component ablation (sequential)
for ablate in none mod24-only mod9-only no-modular; do
  cargo run --release --bin qa_speed_benchmark -- \
    --dim 16 --lr 0.2 --lr-hgd 0.4 --ablate $ablate \
    --log-csv target/qa_ablations/ablate_${ablate}.csv
done
```

### Generate All Plots + JSON
```bash
make qa-plots-raman-ablation
python3 scripts/qa_plot_benchmarks.py --seeds 10 --out plots/qa_seed_stability.png
python3 scripts/qa_plot_ablations.py --out plots/qa_component_ablation.png
python3 qa_agents/cli/qa_paper.py --json-out artifacts/overleaf/qa_paper.json --print
```

---

## Success Metrics (End of Week 1)

- [ ] 3/5 priorities completed (Raman, Seed, Component)
- [ ] JSON receipt includes ≥5 new experiment types
- [ ] Overleaf bundle includes ≥3 new figures
- [ ] 1 ingestion paper (sheaf cohomology) processed and integrated
- [ ] Makefile has ≥3 new targets

---

## Questions for User

1. **Raman ablation:** Should we also test intermediate feature combinations (e.g., grid + mod24-only QA tuples)?

2. **Seed stability:** Is 10 seeds sufficient, or should we do 20 for final publication?

3. **Component ablation:** Should we also ablate `hgd-gain` and `hgd-floor` parameters?

4. **JEPA-MNIST:** Should we use full MNIST (60k images) or a subset (10k) for faster iteration?

5. **Sheaf cohomology:** Should the LaTeX proof be standalone or integrated into main manuscript?

---

**Status:** Roadmap complete; ready to execute Priority 1 (Raman ablation)
