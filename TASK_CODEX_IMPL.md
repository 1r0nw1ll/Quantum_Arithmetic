# TASK FOR CODEX: Implement qa_jepa_encoder.py

**Input**:
- `/tmp/qa_jepa_full.txt`
- `QA_CANONICAL_INVARIANTS.md`
- `qa_toroid_sumproduct.py` (reference)

**Priority**: HIGH
**Type**: Code generation

---

## Your Mission

Create a Python implementation plan and skeleton code for `qa_jepa_encoder.py`

### Core Classes Needed

1. **QAEncoder**: Raw input → QA tuple bundle
2. **QAPredictor**: Evolution operator on QA states
3. **QAHarmonicLoss**: Energy function for QA mismatch
4. **QARotor**: Modular orbit stepper
5. **QAJEPA**: Main wrapper integrating all components

### Requirements

#### QAEncoder Class
```python
class QAEncoder:
    """Encode input patches/tokens/frames to QA tuples"""
    def __init__(self, modulus=24, enforce_constraints=True):
        # Your design here
        pass

    def forward(self, x):
        """
        Args:
            x: Input tensor [batch, channels, ...]
        Returns:
            qa_bundle: Dict with 'b', 'e', 'd', 'a', 'J', 'K', 'X', ...
        """
        pass
```

#### QAPredictor Class
```python
class QAPredictor:
    """Predict future QA state from current + latent"""
    def __init__(self, modulus=24, n_steps=1):
        pass

    def forward(self, s_current, z_latent=None):
        """
        Args:
            s_current: Current QA tuple bundle
            z_latent: Optional resonance mode selection
        Returns:
            s_predicted: Predicted QA tuple bundle
        """
        pass
```

#### QAHarmonicLoss Class
```python
class QAHarmonicLoss:
    """Compute harmonic mismatch between QA states"""
    def __init__(self, weights=None):
        pass

    def forward(self, s_pred, s_target):
        """
        Returns:
            loss: Scalar harmonic mismatch
            metrics: Dict with individual component losses
        """
        pass
```

### Integration Points

Must integrate with:
- `qa_graphrag_utils.py` → E8 alignment computation
- `qa_toroid_sumproduct.py` → Toroidal geometry
- `qa-right-triangle` MCP server → Triangle validation

### Variants to Support

Implement at least 3 variants:
1. **I-JEPA**: Image patches
2. **V-JEPA**: Video frames
3. **TS-JEPA**: Time series

---

## Output Requirements

Save to: `/home/player2/signal_experiments/qa_lab/CODEX_JEPA_IMPL.py`

Include:
- [ ] All 5 core classes with docstrings
- [ ] Type hints
- [ ] Integration hooks for E8/toroid/MCP
- [ ] Example usage for I-JEPA
- [ ] Unit test stubs

Use canonical invariants ONLY (see `QA_CANONICAL_INVARIANTS.md`)

Go!
