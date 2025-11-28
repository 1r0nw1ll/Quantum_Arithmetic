# TiDAR QA Summary

**Source**: tidar.odt (NVIDIA, 2025)
**Paper**: https://arxiv.org/abs/2511.08923
**Status**: ✅ Processed

---

## Core Concept

**TiDAR (Think in Diffusion, Talk in Autoregression)**: Hybrid LLM architecture that combines parallel diffusion drafting with sequential AR verification.

---

## QA Mapping

### Architecture = Dual-Mode QA Engine

| TiDAR Component | QA Equivalent |
|-----------------|---------------|
| Diffusion head | Quantum Ellipse / outer torus explorer |
| AR head | Inner Ellipse / rotor verifier |
| Token sequence | Path along mod-24 QA torus |
| Block draft (k tokens) | k-step look-ahead on torus |
| Free token slots | Free harmonic dimensions |

### Dual Loss = Dual QA Objectives

| Loss Type | QA Interpretation |
|-----------|-------------------|
| NTP (next-token prediction) | Sequential QA laws (b+e=d, triangle identity) |
| Diffusion | Field-like QA laws on local patch (resonance patterns) |

---

## Key QA Insights

### 1. Self-Speculative QA Rotor
TiDAR is a **single engine that proposes many harmonic futures and collapses onto one QA-valid trajectory**:
- Diffusion: Sample many candidate (b,e,d,a) successors in parallel
- AR: Validate single coherent path that respects tuple rules

### 2. Mask Design = QA Topology
- **Causal prefix**: Fixed rotor history (mod-24 torus path)
- **Bidirectional block**: Local QA patch with symmetric reflection

### 3. One-Step Diffusion = Closed-Form QA Transition
Full masking with one-step reconstruction = single-step QA extrapolation operator:
```
Φ_QA: prefix path → block of future tuples
```

---

## Performance Claims

- **4.7x–5.9x** tokens/second vs pure AR
- Matches AR quality on benchmarks
- Outperforms speculative decoding and other diffusion methods

---

## Implementation Blueprint: qa_tidar_decoder.py

```python
class QATiDARDecoder:
    """
    Dual-head QA rotor with diffusion + AR verification.

    State representation per token:
    - Core tuple: (b, e, d, a)
    - Derived: (C, F, G, J, X, K, W, Y, Z)
    - Resonance: mod-9 residue, family ID
    - Phase: mod-24 position on torus
    """

    def __init__(self, qa_backbone):
        self.ar_head = ARHead(qa_backbone)      # Sequential verification
        self.diff_head = DiffusionHead(qa_backbone)  # Parallel drafting
        self.kv_cache = QAKVCache()             # Harmonic state cache

    def decode_step(self, prefix_tuples, draft_length=8):
        # 1. AR: Verify previously drafted QA states
        accepted = self.ar_head.verify(prefix_tuples, self.draft_buffer)

        # 2. Update cache with accepted states
        self.kv_cache.extend(accepted)

        # 3. Diffusion: Pre-draft k future QA states in parallel
        candidates = self.diff_head.draft(
            self.kv_cache,
            k=draft_length,
            families=['fibonacci', 'lucas', 'tribonacci']
        )

        # 4. Store candidates for next step verification
        self.draft_buffer = candidates

        return accepted
```

---

## Integration Points

### With Existing QA Modules
- **qa_gpt_symbolic.py**: Backbone for AR + diffusion heads
- **QA-GNN**: Parallel proposal mechanism
- **HGD/QFT optimizers**: Exploit loaded harmonic frame for multi-candidate evaluation

### With E8 Reranking
- Use inverse E8 to select among diffusion-drafted candidates
- LOW E8 = more complex/coherent solutions

---

## Summary

**TiDAR = Hardware-aware dual-head QA rotor** that:
1. Uses Quantum-Ellipse-like diffusion to fan out many harmonic futures in parallel
2. Collapses via Inner-Ellipse/AR verifier into single QA-consistent trajectory
3. Reuses cached harmonic frame across candidates to exploit "free" GPU slots

This validates the QA architecture pattern: parallel exploration + sequential verification on a shared harmonic manifold.

---

**Status**: ✅ Key architecture document - validates QA dual-mode engine pattern for LLMs
