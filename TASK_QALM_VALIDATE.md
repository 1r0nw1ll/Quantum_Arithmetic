# TASK FOR QALM: Validate QA-JEPA Against Existing QA Code

**Input**:
- `QA_CANONICAL_INVARIANTS.md`
- `/tmp/qa_jepa_full.txt`
- `qa_toroid_sumproduct.py`
- `qa_graphrag_utils.py`

**Priority**: HIGH
**Type**: Validation & Testing

---

## Your Mission

As the QA-specialized model, validate that the QA-JEPA integration respects all canonical QA properties.

### Validation Checklist

#### 1. Invariant Consistency
Verify proposed QA-JEPA formulas maintain:
- [ ] J = b·d, K = d·a, X = e·d
- [ ] W = X + K closure
- [ ] Y = A - D = a² - d²
- [ ] Z = E + K = e² + da
- [ ] Pythagorean: C² + F² = G²

#### 2. Tuple Constraints
Check that any QA encoding preserves:
- [ ] b + e = d
- [ ] e + d = a (or b + 2e = a)
- [ ] All values positive integers/rationals
- [ ] Mod-9 residues {1..9} (no zero)
- [ ] Mod-24 residues {1..24} (no zero)

#### 3. E8 Alignment
Test proposed encodings:
- [ ] Can compute E8 alignment using existing code
- [ ] Values reasonable (0-1 range expected)
- [ ] High-resonance tuples (e.g. Fibonacci) show elevated scores

#### 4. Toroidal Geometry
Verify mappings respect:
- [ ] Torus parameters (R, r, a, b, k) derivable from triangles
- [ ] (m,n) winding numbers consistent with mod-24/mod-9
- [ ] AP vs GP classification works correctly

### Test Cases

Run these specific validations:

**Test 1**: Grant's LRT (1,2,3,5)
```python
b, e, d, a = 1, 2, 3, 5
# Verify all invariants
# Expected: C=12, F=5, G=13, E8≈0.906
```

**Test 2**: Satellite Family (3,5,8,13)
```python
b, e, d, a = 3, 5, 8, 13
# Check 8-cycle classification
# Verify W, Y, Z formulas
```

**Test 3**: Singularity (9,9,18,27)
```python
b, e, d, a = 9, 9, 18, 27
# Special case - verify stability
```

---

## Output Requirements

Save to: `/home/player2/signal_experiments/qa_lab/QALM_VALIDATION_REPORT.md`

**Format**:
```markdown
# QA-JEPA Validation Report by QALM

## Summary
✅ PASS / ❌ FAIL / ⚠️ WARNING

## Invariant Tests
[Checklist results with examples]

## Constraint Verification
[Which formulas passed/failed]

## Integration Issues Found
[List any problems with proposed QA-JEPA code]

## Recommendations
[How to fix any issues]

## Test Results
[Specific numbers for Test 1, 2, 3]
```

---

## Constraints

- Use **ONLY** canonical invariants from `QA_CANONICAL_INVARIANTS.md`
- Cross-check against `qa_toroid_sumproduct.py` (known working code)
- Cite specific line numbers when finding issues

---

## Success Criteria

- [ ] All 3 test cases run successfully
- [ ] Invariant formulas verified
- [ ] Any errors clearly documented
- [ ] Recommendations provided

Go!
