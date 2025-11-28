# QA Canonical Invariants - AUTHORITATIVE REFERENCE

**DO NOT DEVIATE FROM THESE DEFINITIONS**
**Source**: context2.txt:1296-1377, verified 2025-11-20

---

## Core QA Tuple

**Constraints**:
- b + e = d
- e + d = a
(or b + 2e = a)

**Square terms**:
- D = d²
- E = e²
- A = a²
- B = b²

---

## Primary Invariants (J, K, X)

```
J = b · d    (perigee - closest point to center)
K = d · a    (apogee - furthest point from center)
X = e · d    (half distance between foci, C/2)
```

---

## Secondary Invariants (W, Y, Z)

```
W = d(e + a) = X + K = ed + da
   (Side of equilateral triangle)

Y = A - D = a² - d²
   (Related to Eisenstein triples)

Z = E + K = e² + da = e² + (a·d)
```

---

## Right Triangle Sides (C, F, G)

```
C = 2·e·d = 2X    (long leg, focal separation)
F = b·a           (short leg, altitude)
G = e² + d² = E + D    (hypotenuse)
```

**Pythagorean property**: C² + F² = G²
(This is AUTOMATIC from the QA constraints, not an additional axiom)

---

## Ellipse Radii

**Quantum Ellipse** (full scale):
- Semi-major axis = d²
- Focal distance = C = 2ed
- Perigee = J = bd
- Apogee = K = da

**Inner Ellipse** (divided by d):
- Semi-major axis = d
- Radii: b, e, a
- Minor semi-axis = √F = √(ba)

---

## Additional Properties

**Inradius** (right triangle):
```
r = b · e
```
(NOT W - that's a different invariant!)

**Area**:
```
T = (1/2) · C · F = b·e·d·a
L = T/6
```

---

## Modular Reductions

**mod-9** (digital root, {1..9}):
```
value_mod9 = ((value - 1) % 9) + 1
```

**mod-24** (outer cycle, {1..24}):
```
value_mod24 = ((value - 1) % 24) + 1
```

---

## Closure Relations (VERIFY THESE)

From context2.txt:1372-1374:
```
✓ W = K + C/2
✓ Z = E + K
✓ Y = A - D
```

**DO NOT** invent formulas like:
- ❌ b² + e² (not a canonical invariant)
- ❌ W = b·e (that's r, the inradius)
- ❌ Y = W - X (WRONG - it's Y = W - F per user correction)

---

## Eisenstein Triple Connection

**User correction**: Y relates to Eisenstein triples
- Y = A - D = a² - d²
- **Y = W - F** (user-provided formula)
- Where W = X + K and F = ba

This needs further documentation from vault files on Eisenstein triples.

---

## Sources & Verification

1. **context2.txt:1296-1377** - Primary definitions
2. **context2.txt:1317-1322** - W, Y, Z formulas
3. **User correction 2025-11-20**: Y = W - F (Eisenstein connection)
4. **Vault files**: 13 files mentioning Eisenstein (needs extraction)

---

## Usage in Code

**ALWAYS verify**:
1. Use J, K, X as defined (b·d, d·a, e·d)
2. Check W = X + K closure
3. Verify Pythagorean: C² + F² = G²
4. Apply correct mod-9/mod-24 formulas (no zero element)

**NEVER**:
- Redefine J, K, X
- Mix up quantum vs inner ellipse formulas
- Forget that r = be (inradius)
- Confuse W with other invariants

---

**Last Updated**: 2025-11-20
**Status**: CANONICAL - Do not modify without user approval
