# Real Model E8 Results

**Date**: 2025-11-21
**Status**: Completed - Important finding

---

## Experiment

Tested inverse E8 reranking on REAL neural network outputs instead of synthetic perturbations.

### Method
- Simple CNN trained per-task (30 epochs each)
- Generated 10 candidates via temperature sampling
- Inserted correct solution at random position
- Tested inverse E8 reranking

---

## Results

| Metric | Value |
|--------|-------|
| Inverse E8 accuracy | **12%** (6/50) |
| E8 discrimination rate | 34% |
| Model greedy accuracy | 2% |
| Random baseline | 10% |

---

## Key Finding

**Inverse E8 works on SYNTHETIC perturbations (86.5%) but NOT on real model outputs (12%).**

### Why?

1. **Synthetic test was favorable**: Correct solutions are structurally simpler than random pixel perturbations
2. **Real outputs are different**: Untrained model outputs are wrong in random ways, not "perturbed correct"
3. **Low discrimination**: E8 only differentiated 34% of tasks on real outputs

---

## Implications

### Where Inverse E8 Works
- Verifying known-correct solutions against random perturbations
- Detecting if a candidate is structurally "correct-like"
- Post-processing for well-trained models

### Where It Doesn't Work
- Reranking random/untrained model outputs
- Cases where all candidates are equally wrong

---

## Conclusion

Inverse E8 is a **structural complexity detector**, not a universal quality metric. It works best when:
- Correct solution has inherent structural simplicity
- Candidates include "nearly correct" options

For production use: Combine with a well-trained base model where inverse E8 can distinguish good-but-close from random.

---

**Files**:
- `arc_cnn_solver.py` - Test implementation
- `real_vit_e8_results.json` - Raw results
