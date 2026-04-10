# QA ↔ SVP Cross-Domain Validation Package

Prepared by Claude (QA Lab) — 2026-04-03

## What's In This Package

### Scripts (Python 3.10+, numpy + sklearn required)

| File | Purpose | Run |
|---|---|---|
| `qa_svp_validation_harness.py` | **Main harness** — runs any time-series through the full QA→SVP pipeline | `python qa_svp_validation_harness.py` |
| `qa_svp_toroidal_flow_experiment.py` | Validates the QA orbit ↔ SVP toroidal flow correspondence | `python qa_svp_toroidal_flow_experiment.py` |

### Pre-computed Results

| File | Contents |
|---|---|
| `results/qa_svp_harness_results.json` | Summary across all 10 demo signals |
| `results/qa_svp_harness_<signal>.json` | Per-signal detailed output (state sequences, QCI, orbits, transitions) |
| `results/qa_svp_toroidal_flow_results.json` | Toroidal mapping experiment results |
| `results/qa_svp_toroidal_flow.png` | Visualization: flow score distributions + cross-tab heatmaps |

### Dependencies

```
numpy
scikit-learn   # optional — falls back to quantile binning without it
scipy          # optional — only for target correlation
matplotlib     # only needed for toroidal_flow_experiment visualization
```

## Quick Start

```bash
# Run the harness on built-in demo signals
python qa_svp_validation_harness.py

# Run on your own signal
python3 -c "
from qa_svp_validation_harness import QASVPHarness, HarnessConfig
import numpy as np

# Load your signal (any 1D or multi-channel time series)
signal = np.loadtxt('your_signal.csv')

harness = QASVPHarness(HarnessConfig(modulus=24, n_clusters=6))
result = harness.run(signal, name='your_signal')
result.to_json('your_signal_qa_svp.json')
"
```

## How To Compare With SVP

1. **Pick a signal** — use one of the 10 demo signals, or provide your own
2. **Load the QA results** from `results/qa_svp_harness_<signal>.json`
3. **Run SVP harmonic analysis** on the same raw signal independently
4. **Compare these fields:**

| QA Output Field | What It Measures | SVP Comparison Point |
|---|---|---|
| `toroidal_flow.fractions` | Distribution of outward/equilibrium/inward | SVP dominant/harmonic/enharmonic ratios |
| `toroidal_flow.flow_score_stats` | Torus diversity metric | SVP field intensity/complexity |
| `orbit_transitions.transition_matrix` | P[family_i → family_j] | SVP flow mode transition probabilities |
| `svp_phase_transitions.transition_type_counts` | Named SVP transitions (expansion, collapse, etc.) | Direct comparison to SVP-observed events |
| `qci_series` | Rolling coherence index (0-1) | SVP coherence/resonance metric |
| `qa_state_sequence` | Full discrete state series {1,...,24} | Re-analyzable with any method |

## SVP Phase Transition Glossary

These six transition types are detected automatically:

| Transition | From → To | SVP Interpretation |
|---|---|---|
| **Expansion** | equilibrium → outward | Field breaks containment, radiates |
| **Containment** | outward → equilibrium | Radiant field stabilizes |
| **Collapse** | outward → inward | Radiant field collapses to center |
| **Eruption** | inward → outward | Collapsed field explodes outward |
| **Decay** | equilibrium → inward | Balanced field degrades |
| **Revival** | inward → equilibrium | Convergent field re-stabilizes |

## QA ↔ SVP Correspondence (Validated)

| SVP Flow | QA Orbit | Torus Geometry | Agreement |
|---|---|---|---|
| Outward (centrifugal) | Cosmos (24-cycle) | High R/r, thin torus, high diversity | 100% mod 9, 100% mod 24 |
| Equilibrium (balanced) | Satellite (8-cycle) | Moderate R/r, fat torus, low diversity | 100% mod 9, 32% mod 24 |
| Inward (centripetal) | Singularity (1-cycle) | Degenerate (collapsed) | 100% both |

## Key Numbers

- QA modulus: 24 (applied layer) — states in {1,...,24}
- 3 orbit families: cosmos (24-cycle), satellite (8-cycle), singularity (fixed point)
- 6 certified cross-domain results: finance, EEG, audio, climate, cardiac, EMG
- QCI = T-operator coherence index: predicts state[t+2] from states at t and t+1
- Strongest domain result: audio (r = +0.75)

## Contact

Will Player — QA Lab
