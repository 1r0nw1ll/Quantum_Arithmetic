# ARC Vision Integration Status

**Date**: 2025-11-20
**Status**: 📋 ANALYZED - Ready for implementation
**Analysis**: Gemini (GEMINI_ARC_VISION_ANALYSIS.md)

---

## Executive Summary

Gemini's analysis of the MIT paper "ARC is a Vision Problem" identifies strong opportunities for QA integration. The paper achieves 54.5% on ARC-AGI-1 using a 66M parameter Vision Transformer, but can potentially be enhanced by combining visual and algebraic reasoning through a hybrid QA-Vision architecture.

**Core Insight**: ARC grid puzzles are both visual (spatial patterns) and algebraic (rule-based transformations). QA can provide the algebraic structure that pure vision models lack.

---

## Key Findings from MIT Paper

### 1. Core Methodology

**Vision Transformer (ViT)**:
- 66M parameters
- Image-to-image translation framework
- 30×30 grid inputs → 30×30 grid outputs

**Performance**:
- **ARC-AGI-1**: 54.5% (60.4% with ensembling)
- **ARC-AGI-2**: 8.3% (11.1% with ensembling)
- Ensembling provides ~6-3% improvement

**Key Innovation**: Treat reasoning tasks as pure vision problems, no explicit rule induction

### 2. Pattern Types in ARC

#### Geometric Patterns
- **Symmetries**: Rotation (90°, 180°, 270°), reflection (H/V/diagonal)
- **Scaling**: Objects scaled up/down, pattern repetition
- **Color Transformations**: Systematic color changes/swaps
- **Grid Relationships**: Corner/edge movements, boundary patterns

#### Logical Patterns
- **Rule-based Transformations**: Consistent logical rules across examples
- **Object Tracking**: Following state changes across frames
- **Part-Whole Relationships**: Compositional object structure
- **Multi-step Reasoning**: Combining multiple rules

#### Difficulty Spectrum
- **ARC-AGI-1**: More visual, directly tied to spatial transformations
- **ARC-AGI-2**: More abstract, requires symbolic/logical inference
- **Gap**: 54.5% → 8.3% shows vision alone struggles with abstraction

---

## QA Integration Opportunities (from Gemini)

### 1. Grid → QA Tuple Encoding

**Proposed Mapping**:
```python
# For grid cell at (row, col) with color c:
(b, e, d, a) = (row, col, row + col, row + 2*col)
# Color c stored as tuple feature
```

**Benefits**:
- Preserves spatial relationships algebraically
- Satisfies QA constraints: b+e=d, e+d=a (automatically)
- Enables modular arithmetic on grid positions

**Alternative Encoding**:
```python
# Color-centric encoding
(b, e, d, a) = (c, row, c + row, c + 2*row)
# Or: (c, col, c + col, c + 2*col)
```

### 2. Pattern → QA Orbit Mapping

**Symmetries as QA Transformations**:
- **Rotation 90°**: Specific orbit transformation on (b,e,d,a)
- **Reflection**: Mirror operation on tuple components
- **Translation**: Modular shift on b,e,d,a

**Scaling as Progressions**:
- **Geometric scaling**: Maps to arithmetic progressions in QA tuples
- **Repetition patterns**: Periodic orbits on mod-24 torus

### 3. Color → Modular Arithmetic

**10 Colors (0-9) to QA Moduli**:
- **mod-9 system**: Direct mapping of colors 0-8 (color 9 wraps)
- **mod-24 system**: More complex periodic color transformations
- **Color operations**: Addition, multiplication as modular operations

**Color Transformations as QA Operations**:
```python
# Color swap: c1 ↔ c2
# QA: (b, c1, d, a) → (b, c2, d, a) with modular adjustment

# Color progression: c → (c+k) mod 10
# QA: Orbit evolution with step size k
```

### 4. E8 Alignment for Pattern Quality

**High E8 → High-Quality Patterns**:
- Fibonacci-like spatial arrangements: E8 ≈ 1.0
- Harmonic color progressions: High E8 alignment
- Irregular/chaotic patterns: Low E8 alignment

**Applications**:
1. **Solution Re-ranking**: Among multiple ViT outputs, prefer high E8
2. **Attention Bias**: Focus ViT attention on high-E8 grid regions
3. **Loss Augmentation**: Add E8 alignment term to training loss

---

## Proposed Hybrid Architecture

### 5.1 Dual-Branch Design

```
Input: 30×30 ARC Grid
    ├─ Vision Branch: ViT (66M params)
    │   └─ Patch embedding → Transformer → Visual features
    │
    └─ Algebraic Branch: QA-JEPA Encoder
        └─ Grid → QA tuples → QA invariants (J,K,X,W,Y,Z)

Fusion Layer: Concatenate [Visual features | QA invariants]
    ↓
Decoder: Reconstruct 30×30 output grid
```

### 5.2 QA-Enhanced Embeddings

**QA Invariants as Features**:
For each grid patch (e.g., 5×5 region):
```python
qa_features = [
    J,  # Perigee (b·d)
    K,  # Apogee (d·a)
    X,  # Half focal distance (e·d)
    W,  # d(e+a)
    Y,  # a²-d² (Eisenstein)
    Z,  # e²+K
    e8_alignment,  # Pattern quality
    C % 24,  # mod-24 resonance
    F % 9    # mod-9 resonance
]
```

Concatenate with ViT patch embeddings → richer representation

### 5.3 Toroidal Attention

**Bipolar Coordinates for Grids**:
- Standard positional encoding: Linear (x, y)
- **Toroidal encoding**: Bipolar (ρ, η) from QA mapping
- **Benefit**: Natural handling of wrap-around patterns, periodic structures

**Attention with Toroidal Distance**:
```python
# Standard: Euclidean distance between patches
dist_euclidean = sqrt((x1-x2)² + (y1-y2)²)

# Toroidal: Distance on torus surface
dist_toroidal = toroidal_metric(qa_tuple1, qa_tuple2)
```

### 5.4 Implementation Sketch (from Gemini)

```python
class QAViTHybrid(nn.Module):
    def __init__(self):
        super().__init__()
        self.vision_encoder = ViT(patch_size=5, dim=512, depth=6, heads=8)
        self.qa_encoder = QAEncoder(modulus=24)  # From qa_jepa_encoder.py
        self.fusion_layer = nn.Linear(512 + 9, 512)  # Visual + 9 QA features
        self.decoder = GridDecoder(dim=512, output_size=(30, 30))

    def forward(self, grid):
        # Vision branch
        visual_features = self.vision_encoder(grid)  # Shape: (batch, n_patches, 512)

        # Algebraic branch
        qa_bundle = self.qa_encoder(grid)  # Encode grid as QA tuples
        qa_invariants = self.extract_invariants(qa_bundle)  # Shape: (batch, n_patches, 9)

        # Fusion
        combined = torch.cat([visual_features, qa_invariants], dim=-1)
        fused_features = self.fusion_layer(combined)

        # Decode to output grid
        output_grid = self.decoder(fused_features)
        return output_grid

    def extract_invariants(self, qa_bundle):
        """Compute QA invariants (J,K,X,W,Y,Z, E8, mod-24, mod-9) for each patch."""
        # Implementation using qa_e8_alignment.py and QA_CANONICAL_INVARIANTS.md
        pass
```

---

## Recommendations from Gemini

### 6.1 Immediate Experiments (Low Effort)

1. **E8 as Re-ranker**:
   - Use existing ViT model (54.5% baseline)
   - Generate N candidate solutions
   - Compute E8 alignment for each
   - Re-rank by E8 score
   - **Expected**: 2-5% improvement

2. **QA Invariants as Features**:
   - Augment ViT input with pre-computed QA invariants
   - Add 9 extra input channels
   - Fine-tune existing ViT
   - **Expected**: 3-7% improvement

### 6.2 Full Implementation Plan (High Effort)

1. **Develop `QAGridEncoder`**:
   ```python
   class QAGridEncoder:
       def encode_grid(self, grid: torch.Tensor) -> Dict[str, torch.Tensor]:
           """Convert 30×30 grid to QA tuple bundle."""
           # Map (row, col, color) → (b, e, d, a)
           # Return bundle with all QA invariants
   ```

2. **Implement Dual-Branch Model**:
   - Vision branch: Standard ViT (use existing)
   - Algebraic branch: QA-JEPA encoder from `qa_jepa_encoder.py`
   - Fusion: Attention-based or concatenation

3. **Define QA-based Loss**:
   ```python
   total_loss = pixel_loss + λ * qa_harmonic_loss

   # Where:
   # pixel_loss = CrossEntropy(predicted_grid, target_grid)
   # qa_harmonic_loss = QAHarmonicLoss from qa_jepa_encoder.py
   # λ = weight hyperparameter (start with 0.1)
   ```

### 6.3 Expected Improvements

**Quantitative Predictions**:
- **ARC-AGI-1**: 54.5% → 60-65% (hybrid model)
- **ARC-AGI-2**: 8.3% → 15-20% (hybrid model)
- **Biggest gains on**: Logical/arithmetic tasks where QA provides inductive bias

**Qualitative Benefits**:
- **Improved Generalization**: QA constraints help with few-shot learning
- **Better Abstract Reasoning**: Algebraic branch handles symbolic transformations
- **Interpretability**: QA invariants provide explainable features

---

## Integration with Existing QA Codebase

### Available Modules

**qa_jepa_encoder.py** (540 lines):
- `QAEncoder`: Can encode ARC grids as QA tuples
- `QAPredictor`: Can predict grid transformations
- `QAHarmonicLoss`: Loss function for algebraic consistency
- **Status**: ✅ Production-ready, 100% test pass rate

**qa_e8_alignment.py** (280 lines):
- `e8_alignment_batch_torch()`: Batch E8 computation
- `compute_harmonic_index()`: Quality metric
- **Status**: ✅ Production-ready, validated on Grant's LRT

**QA_CANONICAL_INVARIANTS.md**:
- Complete formula reference for J, K, X, W, Y, Z
- **Status**: ✅ Authoritative reference

**qa_toroid_sumproduct.py** (285 lines):
- Additive vs multiplicative structure detection
- Could classify ARC pattern types
- **Status**: ✅ Working, conceptual (not geometric)

### Integration Hooks

**1. Grid Encoding**:
```python
from qa_jepa_encoder import QAEncoder

encoder = QAEncoder(modulus=24, mode='embed')
qa_bundle = encoder(arc_grid)  # Returns (b, e, d, a) tuples + invariants
```

**2. E8 Re-ranking**:
```python
from qa_e8_alignment import e8_alignment_batch_torch

# For N candidate solutions
e8_scores = e8_alignment_batch_torch(b, e, d, a)
best_idx = torch.argmax(e8_scores)
best_solution = candidates[best_idx]
```

**3. Harmonic Loss**:
```python
from qa_jepa_encoder import QAHarmonicLoss

qa_loss = QAHarmonicLoss()
harmonic_penalty = qa_loss(predicted_qa_bundle, target_qa_bundle)
total_loss = pixel_loss + 0.1 * harmonic_penalty
```

---

## Technical Challenges

### 1. Grid → QA Tuple Mapping

**Challenge**: ARC grids are 30×30 = 900 cells, need efficient encoding

**Solutions**:
- **Patch-based**: Encode 5×5 patches (36 patches total)
- **Sparse**: Only encode non-background cells
- **Hierarchical**: Multi-scale QA tuples (cell-level + patch-level)

### 2. Color Representation

**Challenge**: 10 colors don't align perfectly with mod-9 or mod-24

**Solutions**:
- **mod-9**: Map color 9 → 0 (wrap-around)
- **mod-24**: Use colors 0-9, leave 10-23 for intermediate states
- **One-hot + QA**: Hybrid representation

### 3. Computational Cost

**Challenge**: Dual-branch model is heavier than pure ViT

**Solutions**:
- **Lightweight QA branch**: Smaller QA encoder (fewer layers)
- **Selective fusion**: Only fuse at certain layers
- **Inference optimization**: Cache QA computations

---

## Validation Strategy

### Test Plan

1. **Baseline**: Reproduce MIT ViT results (54.5% on ARC-AGI-1)
2. **E8 Re-ranking**: Test on ARC-AGI-1 validation set
3. **QA Features**: Fine-tune with QA invariants
4. **Hybrid Model**: Full dual-branch architecture
5. **ARC-AGI-2**: Test on harder benchmark

### Metrics

**Primary**:
- Accuracy on ARC-AGI-1/2 test sets
- Ensemble vs single model

**Secondary**:
- E8 alignment of correct vs incorrect solutions
- QA harmonic loss correlation with accuracy
- Ablation: Vision-only vs QA-only vs Hybrid

### Success Criteria

**Minimal Success**:
- E8 re-ranking improves baseline by ≥2%
- QA features improve by ≥3%

**Strong Success**:
- Hybrid model achieves ≥60% on ARC-AGI-1
- Hybrid model achieves ≥15% on ARC-AGI-2

**Breakthrough**:
- Hybrid model achieves ≥65% on ARC-AGI-1
- Hybrid model achieves ≥20% on ARC-AGI-2

---

## Connection to QA Research Goals

### Why This Matters

1. **Real-World Benchmark**: ARC is a standard AGI benchmark, not toy data
2. **Visual + Algebraic**: Tests QA's claim to provide universal structure
3. **Few-Shot Learning**: ARC tasks have 2-5 examples, tests generalization
4. **Symbolic Reasoning**: ARC-AGI-2 requires abstraction, ideal for QA

### Broader Impact

**If successful, this demonstrates**:
- QA can enhance SOTA vision models
- Algebraic structure improves abstract reasoning
- Hybrid architectures > pure vision or pure symbolic

**Potential Applications**:
- Visual theorem proving
- Geometric puzzle solving
- Automated pattern discovery in images

---

## Next Steps

### Immediate (1-2 days)

1. ✅ Extract ARC paper (DONE)
2. ✅ Analyze and propose QA integration (DONE - Gemini)
3. ⏭️ Implement `QAGridEncoder` module
4. ⏭️ Test E8 re-ranking on ARC validation set

### Short Term (1-2 weeks)

1. Fine-tune ViT with QA invariants as features
2. Implement dual-branch architecture
3. Train on ARC-AGI-1 training set
4. Validate on ARC-AGI-1 test set

### Long Term (1-2 months)

1. Optimize hybrid architecture
2. Test on ARC-AGI-2
3. Publish results (paper or blog post)
4. Open-source `QAArcSolver` module

---

## Related Work

### Similar Approaches

**Neuro-Symbolic AI**:
- Combines neural networks + symbolic reasoning
- QA hybrid is similar but with geometric/algebraic structure

**Program Synthesis for ARC**:
- Learns programs to solve ARC tasks
- QA approach is more implicit (learned transformations)

**Geometric Deep Learning**:
- Exploits geometric structure in data
- QA toroidal geometry is related concept

---

## Conclusion

**Key Insight**: MIT's vision-only approach achieves 54.5% but struggles on abstract reasoning (8.3% on ARC-AGI-2). Adding QA's algebraic structure provides:

1. **Inductive Bias**: Grid patterns have algebraic structure
2. **Pattern Quality**: E8 alignment measures harmonic coherence
3. **Explicit Reasoning**: QA invariants capture symbolic relationships

**Status**: ✅ Analyzed, concrete implementation plan ready

**Next Action**: Implement `QAGridEncoder` and test E8 re-ranking

**Expected Impact**: 5-15% improvement on ARC-AGI-1, larger gains on ARC-AGI-2

---

**Analysis By**: Gemini (Nov 20, 2025)
**Integration By**: Claude Code (Sonnet 4.5)
**Documents Processed**: 7/22 ingestion candidates (32%)
**Next**: Continue ingestion OR begin ARC implementation

