"""
qa_fastpath.py - QA fast-path utilities (reranking and gating)

Provides:
- fast_rerank_by_e8: Rust-accelerated E8 alignment reranker
- mod24_gate, digital_root_gate: cheap modular filters

Usage:
  from qa_fastpath import fast_rerank_by_e8
  idx = fast_rerank_by_e8(b,e,d,a, e8_roots, topk=64)
"""
from __future__ import annotations

import numpy as np
from typing import Sequence, Tuple, Optional, Iterable, Dict
import os

def harmonic_index(e8: np.ndarray, loss: np.ndarray, k: float = 0.25) -> np.ndarray:
    e8 = np.asarray(e8, dtype=np.float64)
    loss = np.asarray(loss, dtype=np.float64)
    try:
        if _rs is not None and hasattr(_rs, 'harmonic_index_batch_numpy_py'):
            return _rs.harmonic_index_batch_numpy_py(e8, loss, float(k))
    except Exception:
        pass
    return e8 * np.exp(-float(k) * loss)

try:
    import qa_lab_rs as _rs
except Exception:
    _rs = None

try:
    from qa_rust_bridge import compute_all as _compute_all, rust_available as _rust_available
except Exception:
    _compute_all = None
    def _rust_available():
        return False


def build_e8_vectors(b: np.ndarray, e: np.ndarray, d: np.ndarray, a: np.ndarray) -> np.ndarray:
    """Construct 8D vectors [b,e,d,a,J,K,X,W] for E8 alignment.
    Uses Rust batch invariants if available; else NumPy fallback.
    """
    if _rust_available() and _compute_all is not None:
        # Fabricate torch-like inputs as numpy arrays; bridge handles numpy → torch
        out = _compute_all(b, e, d, a)
        if out is not None:
            J, K, X, W = out['J'].cpu().numpy(), out['K'].cpu().numpy(), out['X'].cpu().numpy(), out['W'].cpu().numpy()
            return np.stack([b, e, d, a, J, K, X, W], axis=-1)

    # NumPy fallback
    J = d * b
    K = d * a
    X = e * d
    W = X + K
    return np.stack([b, e, d, a, J, K, X, W], axis=-1)


def fast_rerank_by_e8(
    b: Sequence[float], e: Sequence[float], d: Sequence[float], a: Sequence[float],
    e8_roots: np.ndarray, topk: int = 64
) -> np.ndarray:
    """Return indices of top-k candidates by E8 alignment.

    Args:
        b,e,d,a: lists/arrays of equal length
        e8_roots: (M,8) ndarray of roots
        topk: number of candidates to keep
    Returns:
        1D numpy array of indices sorted by score desc
    """
    b = np.asarray(b, dtype=np.float64)
    e = np.asarray(e, dtype=np.float64)
    d = np.asarray(d, dtype=np.float64)
    a = np.asarray(a, dtype=np.float64)
    assert b.shape == e.shape == d.shape == a.shape

    vecs = build_e8_vectors(b, e, d, a)
    if _rs is None:
        # Fallback cosine vs roots in NumPy
        # Normalize vecs and roots
        v_norm = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-12
        r_norm = np.linalg.norm(e8_roots, axis=1, keepdims=True) + 1e-12
        v_unit = vecs / v_norm
        r_unit = e8_roots / r_norm
        sims = v_unit @ r_unit.T
        scores = (sims.max(axis=1) + 1.0) / 2.0
    else:
        scores = e8_scores_auto(vecs, e8_roots)

    idx = np.argsort(-scores)
    return idx[: min(topk, idx.shape[0])]


def mod24_gate(x: Sequence[float], allowed: Sequence[int]) -> np.ndarray:
    """Return boolean mask where x mod 24 in allowed set (ints)."""
    x = np.asarray(x, dtype=np.float64)
    if _rs is not None:
        m = _rs.mod24_batch_numpy_py(x)
    else:
        m = np.mod(x, 24.0)
        m[m < 0] += 24.0
    allowed = set(int(v) % 24 for v in allowed)
    return np.vectorize(lambda v: int(v) in allowed)(m)


def digital_root_gate(x: Sequence[float], allowed: Sequence[int]) -> np.ndarray:
    """Return boolean mask where digital_root(trunc(x)) in allowed."""
    x = np.asarray(x, dtype=np.float64)
    if _rs is not None:
        dr = _rs.digital_root_batch_numpy_py(x)
    else:
        dr = np.vectorize(_digital_root_py)(x)
    allowed = set(int(v) for v in allowed)
    return np.vectorize(lambda v: int(v) in allowed)(dr)


def wheel_gate_d_a(d: Sequence[float], a: Sequence[float], allowed: Iterable[int] = (1,5,7,11)) -> np.ndarray:
    """Return mask where both d mod 24 and a mod 24 fall in prime sectors (default 1,5,7,11)."""
    d = np.asarray(d, dtype=np.float64)
    a = np.asarray(a, dtype=np.float64)
    if _rs is not None:
        d_mod = _rs.mod24_batch_numpy_py(d)
        a_mod = _rs.mod24_batch_numpy_py(a)
    else:
        d_mod = np.mod(d, 24.0); d_mod[d_mod < 0] += 24.0
        a_mod = np.mod(a, 24.0); a_mod[a_mod < 0] += 24.0
    allowed = set(int(v) % 24 for v in allowed)
    md = np.vectorize(lambda v: int(v) in allowed)(d_mod)
    ma = np.vectorize(lambda v: int(v) in allowed)(a_mod)
    return np.logical_and(md, ma)


def closure_gate(b: Sequence[float], e: Sequence[float], d: Sequence[float], a: Sequence[float], tol: float = 1e-9) -> np.ndarray:
    """Return mask where closure residual sqrt((b+e-d)^2 + (e+d-a)^2) <= tol."""
    b = np.asarray(b, dtype=np.float64)
    e = np.asarray(e, dtype=np.float64)
    d = np.asarray(d, dtype=np.float64)
    a = np.asarray(a, dtype=np.float64)
    if _rs is not None and hasattr(_rs, 'closure_residual_batch_numpy_py'):
        res = _rs.closure_residual_batch_numpy_py(b, e, d, a)
    else:
        res = np.sqrt((b + e - d) ** 2 + (e + d - a) ** 2)
    return res <= float(tol)


def inner_ellipse_gate(b: Sequence[float], e: Sequence[float], d: Sequence[float], a: Sequence[float], tol: float = 1e-9) -> np.ndarray:
    """Return mask where |a^2 - (d^2 + 2de + e^2)| <= tol."""
    b = np.asarray(b, dtype=np.float64)
    e = np.asarray(e, dtype=np.float64)
    d = np.asarray(d, dtype=np.float64)
    a = np.asarray(a, dtype=np.float64)
    if _rs is not None and hasattr(_rs, 'inner_ellipse_residual_batch_numpy_py'):
        res = _rs.inner_ellipse_residual_batch_numpy_py(b, e, d, a)
    else:
        res = a * a - (d * d + 2.0 * d * e + e * e)
    return np.abs(res) <= float(tol)


def triangle_gate(b: Sequence[float], e: Sequence[float], d: Sequence[float], a: Sequence[float], tol: float = 1e-9) -> np.ndarray:
    """Return mask where |C^2 + F^2 - G^2| <= tol, with C=2ed, F=ba, G=e^2 + d^2."""
    b = np.asarray(b, dtype=np.float64)
    e = np.asarray(e, dtype=np.float64)
    d = np.asarray(d, dtype=np.float64)
    a = np.asarray(a, dtype=np.float64)
    if _rs is not None and hasattr(_rs, 'triangle_residual_batch_numpy_py'):
        res = _rs.triangle_residual_batch_numpy_py(b, e, d, a)
    else:
        c = 2.0 * e * d
        f = b * a
        g = e * e + d * d
        res = np.abs(c*c + f*f - g*g)
    return res <= float(tol)


def family_gate(
    b: Sequence[float], e: Sequence[float], d: Sequence[float], a: Sequence[float],
    phi_tol: float = 0.05
) -> np.ndarray:
    """Gate that keeps tuples close to Fibonacci/Lucas-like families.

    Pass if either a/d ≈ φ or e/b ≈ (φ-1) within tolerance.
    """
    b = np.asarray(b, dtype=np.float64)
    e = np.asarray(e, dtype=np.float64)
    d = np.asarray(d, dtype=np.float64)
    a = np.asarray(a, dtype=np.float64)
    phi = 1.6180339887498948
    denom_d = np.abs(d) + 1e-12
    denom_b = np.abs(b) + 1e-12
    err_ad = np.abs((a / denom_d) - phi)
    err_eb = np.abs((e / denom_b) - (phi - 1.0))
    return (err_ad <= phi_tol) | (err_eb <= phi_tol)


def positivity_gate(
    b: Sequence[float], e: Sequence[float], d: Sequence[float], a: Sequence[float],
    min_value: float = 0.0
) -> np.ndarray:
    """Gate that requires all components >= min_value.

    Useful to enforce geometric positivity constraints before heavier work.
    """
    b = np.asarray(b, dtype=np.float64)
    e = np.asarray(e, dtype=np.float64)
    d = np.asarray(d, dtype=np.float64)
    a = np.asarray(a, dtype=np.float64)
    return (b >= min_value) & (e >= min_value) & (d >= min_value) & (a >= min_value)


def mod9_closure_gate(
    b: Sequence[float], e: Sequence[float], d: Sequence[float], a: Sequence[float]
) -> np.ndarray:
    """Gate that enforces closure in mod-9 (digital-root space with 9-coded zero).

    Uses truncation to non-negative integers as in digital_root_batch_numpy_py.
    Closure in this coding: dr(d) == dr(dr(b)+dr(e)) and dr(a) == dr(dr(e)+dr(d)).
    """
    b = np.asarray(b, dtype=np.float64)
    e = np.asarray(e, dtype=np.float64)
    d = np.asarray(d, dtype=np.float64)
    a = np.asarray(a, dtype=np.float64)
    if _rs is not None:
        dr_b = _rs.digital_root_batch_numpy_py(b)
        dr_e = _rs.digital_root_batch_numpy_py(e)
        dr_d = _rs.digital_root_batch_numpy_py(d)
        dr_a = _rs.digital_root_batch_numpy_py(a)
    else:
        dr_b = np.vectorize(_digital_root_py)(b)
        dr_e = np.vectorize(_digital_root_py)(e)
        dr_d = np.vectorize(_digital_root_py)(d)
        dr_a = np.vectorize(_digital_root_py)(a)
    # 9-coded addition: ((x+y-1) % 9) + 1
    dr_be = ((dr_b + dr_e - 1) % 9) + 1
    dr_ed = ((dr_e + dr_d - 1) % 9) + 1
    ok_d = (dr_d == dr_be)
    ok_a = (dr_a == dr_ed)
    return ok_d & ok_a


def get_e8_roots() -> Optional[Tuple[np.ndarray, bool]]:
    """Load E8 roots from env or default path.

    Returns (roots, roots_are_unit) or None if not found.
    Checks QA_E8_ROOTS_PATH, then qa_lab/data/e8_roots_unit.npy, qa_lab/data/e8_roots.npy.
    """
    import os
    base_candidates = []
    env_path = os.getenv('QA_E8_ROOTS_PATH')
    if env_path:
        base_candidates.append(env_path)
    base_candidates.append('qa_lab/data/e8_roots_unit.npy')
    base_candidates.append('qa_lab/data/e8_roots.npy')
    for p in base_candidates:
        try:
            roots = np.load(p)
            if roots.ndim == 2 and roots.shape[1] == 8:
                norms = np.linalg.norm(roots, axis=1)
                unit_like = np.allclose(norms, 1.0, rtol=1e-6, atol=1e-6)
                return roots, unit_like
        except Exception:
            continue
    return None


def e8_scores_auto(
    vecs: np.ndarray,
    roots: np.ndarray,
    *,
    vec_chunk: Optional[int] = None,
    root_chunk: Optional[int] = None,
) -> np.ndarray:
    """Compute E8 alignment scores with automatic backend selection and chunking.

    If Rust is available, calls Rust batch in chunks (to cap memory) and uses prenorm path if roots are unit.
    Else falls back to NumPy matrix multiply (v_unit @ r_unit.T), with chunking on roots if requested.
    """
    assert vecs.ndim == 2 and vecs.shape[1] == 8
    assert roots.ndim == 2 and roots.shape[1] == 8

    # Strategy flags
    prefer_numpy_env = os.getenv('QA_E8_PREFER_NUMPY', '0') == '1'
    disable_rust_env = os.getenv('QA_E8_DISABLE_RUST', '0') == '1'
    # Heuristic: if NumPy BLAS likely faster (very large M or small N), prefer NumPy path
    N, M = vecs.shape[0], roots.shape[0]
    prefer_numpy = prefer_numpy_env or (_rs is None) or disable_rust_env or (M > 2000 and N < 4096)

    if prefer_numpy:
        v_norm = np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-12
        v_unit = vecs / v_norm
        # Chunk roots if requested or if very large
        if root_chunk is None or root_chunk <= 0:
            rc_env = os.getenv('QA_E8_ROOT_CHUNK')
            if rc_env:
                try:
                    root_chunk = max(1, int(rc_env))
                except Exception:
                    root_chunk = 200_000 if M > 200_000 else M
            else:
                root_chunk = 200_000 if M > 200_000 else M
        best = None
        for start in range(0, M, root_chunk):
            end = min(start + root_chunk, M)
            r_slice = roots[start:end]
            r_norm = np.linalg.norm(r_slice, axis=1, keepdims=True) + 1e-12
            r_unit = r_slice / r_norm
            sims = v_unit @ r_unit.T
            max_part = sims.max(axis=1)
            if best is None:
                best = max_part
            else:
                best = np.maximum(best, max_part)
        return (best + 1.0) / 2.0

    # Rust path with chunking
    unit_like = np.allclose(np.linalg.norm(roots, axis=1), 1.0, rtol=1e-6, atol=1e-6)
    if vec_chunk is None or vec_chunk <= 0:
        vc_env = os.getenv('QA_E8_VEC_CHUNK')
        if vc_env:
            try:
                vec_chunk = max(1, int(vc_env))
            except Exception:
                vec_chunk = 200_000 if N > 200_000 else N
        else:
            vec_chunk = 200_000 if N > 200_000 else N
    # If root_chunk requested, reduce roots in chunks and take max per vector slice
    if root_chunk is None or root_chunk <= 0:
        rc_env = os.getenv('QA_E8_ROOT_CHUNK')
        if rc_env:
            try:
                root_chunk = max(1, int(rc_env))
            except Exception:
                root_chunk = M
        else:
            root_chunk = M  # no chunking across roots
    scores = np.empty(N, dtype=np.float64)
    for start in range(0, N, vec_chunk):
        end = min(start + vec_chunk, N)
        v_slice = vecs[start:end]
        best = None
        for r0 in range(0, M, root_chunk):
            r1 = min(r0 + root_chunk, M)
            roots_slice = roots[r0:r1]
            if unit_like and hasattr(_rs, 'compute_e8_alignment_batch_numpy_prenorm_py'):
                s = _rs.compute_e8_alignment_batch_numpy_prenorm_py(v_slice, roots_slice)
            else:
                s = _rs.compute_e8_alignment_batch_numpy_py(v_slice, roots_slice)
            if best is None:
                best = s
            else:
                best = np.maximum(best, s)
        scores[start:end] = best
    return scores


def fast_prune(
    b: Sequence[float], e: Sequence[float], d: Sequence[float], a: Sequence[float],
    e8_roots: np.ndarray,
    mod24_allowed: Optional[Iterable[int]] = None,
    dr_allowed: Optional[Iterable[int]] = None,
    topk: int = 64,
    e8_chunk: Optional[int] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Combine modular gates and E8 reranking to return pruned indices and scores.

    Returns (keep_idx, scores) where keep_idx are the top-k indices after applying gates.
    """
    b = np.asarray(b, dtype=np.float64)
    e = np.asarray(e, dtype=np.float64)
    d = np.asarray(d, dtype=np.float64)
    a = np.asarray(a, dtype=np.float64)
    assert b.shape == e.shape == d.shape == a.shape
    n = b.shape[0]

    mask = np.ones(n, dtype=bool)
    if mod24_allowed is not None:
        mask &= mod24_gate(d, mod24_allowed)  # example: gating on d mod 24
    if dr_allowed is not None:
        mask &= digital_root_gate(a, dr_allowed)  # example: gating on a digital root

    if not np.any(mask):
        return np.array([], dtype=int), np.array([], dtype=np.float64)

    # E8 rerank on survivors
    idx_pool = np.where(mask)[0]
    vecs = build_e8_vectors(b[idx_pool], e[idx_pool], d[idx_pool], a[idx_pool])
    scores = e8_scores_auto(vecs, np.asarray(e8_roots), vec_chunk=e8_chunk)
    order = np.argsort(-scores)
    keep = idx_pool[order[: min(topk, order.shape[0])]]
    return keep, scores[order[: min(topk, order.shape[0])]]


def _digital_root_array(x: np.ndarray) -> np.ndarray:
    if _rs is not None:
        return _rs.digital_root_batch_numpy_py(x)
    return np.vectorize(_digital_root_py)(x)

# Backward-compat aliases (to be removed): keep qe_* entry points without emitting new QE artifacts
_warned_qe = False

def qe_rank(*args, **kwargs):
    global _warned_qe
    if not _warned_qe:
        try:
            import warnings
            warnings.warn("qe_rank is deprecated; use qa_rank", DeprecationWarning, stacklevel=2)
        except Exception:
            pass
        _warned_qe = True
    return qa_rank(*args, **kwargs)

def qe_prerank(*args, **kwargs):
    global _warned_qe
    if not _warned_qe:
        try:
            import warnings
            warnings.warn("qe_prerank is deprecated; use qa_prerank", DeprecationWarning, stacklevel=2)
        except Exception:
            pass
        _warned_qe = True
    return qa_prerank(*args, **kwargs)


def qa_rank(
    b: Sequence[float], e: Sequence[float], d: Sequence[float], a: Sequence[float],
    *,
    dr_pref: Iterable[int] = (1, 3, 9),
    mod24_pref: Iterable[int] = (1, 5, 7, 11),
    weights: Optional[Dict[str, float]] = None,
) -> np.ndarray:
    """Compute a cheap QA pre-ranking score.

    Features (vectorized):
      - closure: -(|b+e-d| + |e+d-a|)
      - dr_bonus: 1.0 if digital_root(a) in {1,3,9} else 0
      - mod24_bonus: 1.0 if d mod24 in {1,5,7,11} else 0
      - w_est: mean-centered W = d*(e+a)
      - z_est: mean-centered Z = e*e + d*a
    """
    b = np.asarray(b, dtype=np.float64)
    e = np.asarray(e, dtype=np.float64)
    d = np.asarray(d, dtype=np.float64)
    a = np.asarray(a, dtype=np.float64)
    assert b.shape == e.shape == d.shape == a.shape

    # Defaults (curvature weight can be set via env QA_QA_CURV_WEIGHT)
    def _env_float(*keys: str, default: float = 0.0) -> float:
        for k in keys:
            v = os.getenv(k)
            if v is not None:
                try:
                    return float(v)
                except Exception:
                    pass
        return default
    # Prefer QA_QA_* weights; fall back to QA_QE_* for backward compatibility
    _curv_default = _env_float('QA_QA_CURV_WEIGHT', 'QA_QE_CURV_WEIGHT', default=0.0)
    _phi_default = _env_float('QA_QA_PHI_WEIGHT', 'QA_QE_PHI_WEIGHT', default=0.0)
    _phi_eb_default = _env_float('QA_QA_PHI_EB_WEIGHT', 'QA_QE_PHI_EB_WEIGHT', default=0.0)
    _family_default = _env_float('QA_QA_FAMILY_WEIGHT', 'QA_QE_FAMILY_WEIGHT', default=0.0)
    _ideal_default = _env_float('QA_QA_IDEAL_WEIGHT', 'QA_QE_IDEAL_WEIGHT', default=0.0)
    # If Rust scorer-with-invariants is available, reuse Rust invariants first
    if _rs is not None:
        try:
            if hasattr(_rs, 'qe_score_with_inv_batch_numpy_py') and hasattr(_rs, 'compute_bundle_batch_numpy_py'):
                inv = _rs.compute_bundle_batch_numpy_py(b, e, d, a)
                return _rs.qe_score_with_inv_batch_numpy_py(
                    b, e, d, a,
                    inv['W'], inv['Z'], inv['Y'], inv['C'], inv['F'],
                    float(_curv_default), float(_phi_default), float(_phi_eb_default),
                    float(_family_default), float(_ideal_default),
                )
            elif hasattr(_rs, 'qe_score_batch_numpy_py'):
                return _rs.qe_score_batch_numpy_py(
                    b, e, d, a,
                    float(_curv_default), float(_phi_default), float(_phi_eb_default),
                    float(_family_default), float(_ideal_default),
                )
        except Exception:
            pass

    w = {
        'closure': 1.0,
        'dr_bonus': 0.5,
        'mod24_bonus': 0.5,
        'w_est': 0.25,
        'z_est': 0.25,
        'curv': _curv_default,  # nonconventional curvature proxy
        'phi': _phi_default,    # golden-section ratio closeness on a/d
        'phi_eb': _phi_eb_default,  # golden-section ratio closeness on e/b
        'family': _family_default,   # combined family score
        'ideal': _ideal_default,     # quick E8 ideal root cos
    }
    if weights:
        w.update(weights)

    # Features
    closure = - (np.abs(b + e - d) + np.abs(e + d - a))
    dr_vals = _digital_root_array(a)
    dr_set = set(int(v) for v in dr_pref)
    dr_bonus = np.vectorize(lambda v: 1.0 if int(v) in dr_set else 0.0)(dr_vals)

    if _rs is not None:
        d_mod = _rs.mod24_batch_numpy_py(d)
    else:
        d_mod = np.mod(d, 24.0); d_mod[d_mod < 0] += 24.0
    mset = set(int(v) % 24 for v in mod24_pref)
    mod24_bonus = np.vectorize(lambda v: 1.0 if int(v) in mset else 0.0)(d_mod)

    # Cheap invariant estimates
    w_est = d * (e + a)
    z_est = e * e + d * a
    # Curvature proxy (compute only if weighted)
    if w['curv'] != 0.0:
        y_est = a * a - d * d
        c_est = 2.0 * e * d
        f_est = b * a + 1e-12
        curv_ratio = np.abs(y_est) / (np.abs(z_est) + 1e-12)
        curv_cf = np.abs(c_est / f_est)
        curv = np.log1p(curv_ratio) + np.log1p(curv_cf)
    else:
        curv = 0.0
    # Golden ratio closeness on a/d and e/b (compute only if weighted)
    if (w['phi'] != 0.0) or (w['phi_eb'] != 0.0) or (w['family'] != 0.0):
        phi = 1.6180339887498948
        denom = np.abs(d) + 1e-12
        phi_err = -np.abs((a / denom) - phi)
        denom_eb = np.abs(b) + 1e-12
        phi_eb_err = -np.abs((e / denom_eb) - phi)
        family = np.maximum(phi_err, phi_eb_err)
    else:
        phi_err = 0.0
        phi_eb_err = 0.0
        family = 0.0

    # Quick ideal E8 score using [1,1,2,3,0,0,0,0] (absolute cosine) if weighted
    if w['ideal'] != 0.0:
        qa4 = np.stack([b, e, d, a], axis=-1)
        norms4 = np.linalg.norm(qa4, axis=-1) + 1e-12
        qa4u = qa4 / norms4[..., None]
        ideal4 = np.array([1.0, 1.0, 2.0, 3.0], dtype=np.float64)
        ideal4 /= np.linalg.norm(ideal4) + 1e-12
        ideal = np.abs(qa4u @ ideal4)
    else:
        ideal = 0.0

    # Mean-center to keep magnitudes comparable for large-magnitude features
    def _center(x):
        mu = x.mean() if x.size else 0.0
        return x - mu
    w_c = _center(w_est)
    z_c = _center(z_est)

    score = (
        w['closure'] * closure
        + w['dr_bonus'] * dr_bonus
        + w['mod24_bonus'] * mod24_bonus
        + w['w_est'] * w_c
        + w['z_est'] * z_c
        + w['curv'] * curv
        + w['phi_eb'] * phi_eb_err
        + w['phi'] * phi_err
        + w['family'] * family
        + w['ideal'] * ideal
    )
    return score.astype(np.float64)


def qa_prerank(
    b: Sequence[float], e: Sequence[float], d: Sequence[float], a: Sequence[float],
    **kwargs
) -> np.ndarray:
    """Return indices sorted by QA pre-ranking score (desc)."""
    scores = qa_rank(b, e, d, a, **kwargs)
    return np.argsort(-scores)


def fast_prune_and_rank(
    b: Sequence[float], e: Sequence[float], d: Sequence[float], a: Sequence[float],
    e8_roots: np.ndarray,
    *,
    mod24_allowed: Optional[Iterable[int]] = None,
    dr_allowed: Optional[Iterable[int]] = None,
    closure_tol: Optional[float] = None,
    inner_tol: Optional[float] = None,
    triangle_tol: Optional[float] = None,
    family_phi_tol: Optional[float] = None,
    positivity_min: Optional[float] = 0.0,
    ideal_min: Optional[float] = None,
    wheel_allowed: Optional[Iterable[int]] = None,
    qe_topk: int = 2048,
    topk: int = 128,
    e8_chunk: Optional[int] = None,
    qe_kwargs: Optional[Dict[str, float]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Combined pipeline: modular gates → QA pre-ranking → E8 rerank.

    Returns (final_indices, final_scores) where final_scores are E8 scores for the selected indices.
    """
    b = np.asarray(b, dtype=np.float64)
    e = np.asarray(e, dtype=np.float64)
    d = np.asarray(d, dtype=np.float64)
    a = np.asarray(a, dtype=np.float64)
    n = b.shape[0]

    # Environment-driven defaults
    if mod24_allowed is None and os.getenv('QA_FP_ENABLE_WHEEL', '1') == '1':
        mod24_allowed = [1, 5, 7, 11]
    if family_phi_tol is None and os.getenv('QA_FP_ENABLE_FAMILY', '1') == '1':
        try:
            family_phi_tol = float(os.getenv('QA_FP_FAMILY_TOL', '0.05'))
        except Exception:
            family_phi_tol = 0.05
    if positivity_min is None:
        try:
            positivity_min = float(os.getenv('QA_FP_POS_MIN', '0.0'))
        except Exception:
            positivity_min = 0.0

    # Step 1: gates (compute shared intermediates once)
    mask = np.ones(n, dtype=bool)
    d_mod = None
    a_mod = None
    dr_a = None
    need_mod24_d = (mod24_allowed is not None) or (wheel_allowed is not None)
    need_mod24_a = (wheel_allowed is not None)
    if need_mod24_d:
        if _rs is not None:
            d_mod = _rs.mod24_batch_numpy_py(d)
        else:
            d_mod = np.mod(d, 24.0); d_mod[d_mod < 0] += 24.0
    if need_mod24_a:
        if _rs is not None:
            a_mod = _rs.mod24_batch_numpy_py(a)
        else:
            a_mod = np.mod(a, 24.0); a_mod[a_mod < 0] += 24.0
    if dr_allowed is not None:
        if _rs is not None:
            dr_a = _rs.digital_root_batch_numpy_py(a)
        else:
            dr_a = np.vectorize(_digital_root_py)(a)

    if mod24_allowed is not None:
        mset = set(int(v) % 24 for v in mod24_allowed)
        mask &= np.vectorize(lambda v: int(v) in mset)(d_mod)
    if dr_allowed is not None:
        dr_set = set(int(v) for v in dr_allowed)
        mask &= np.vectorize(lambda v: int(v) in dr_set)(dr_a)
    if closure_tol is not None:
        mask &= closure_gate(b, e, d, a, tol=float(closure_tol))
    if inner_tol is not None:
        mask &= inner_ellipse_gate(b, e, d, a, tol=float(inner_tol))
    if triangle_tol is not None:
        mask &= triangle_gate(b, e, d, a, tol=float(triangle_tol))
    if wheel_allowed is not None:
        mset = set(int(v) % 24 for v in wheel_allowed)
        md = np.vectorize(lambda v: int(v) in mset)(d_mod)
        ma = np.vectorize(lambda v: int(v) in mset)(a_mod)
        mask &= np.logical_and(md, ma)
    if family_phi_tol is not None:
        mask &= family_gate(b, e, d, a, phi_tol=float(family_phi_tol))
    if positivity_min is not None:
        mask &= positivity_gate(b, e, d, a, min_value=float(positivity_min))
    if ideal_min is not None:
        # quick ideal gate
        qa4 = np.stack([b, e, d, a], axis=-1)
        norms4 = np.linalg.norm(qa4, axis=-1) + 1e-12
        qa4u = qa4 / norms4[..., None]
        ideal4 = np.array([1.0, 1.0, 2.0, 3.0], dtype=np.float64)
        ideal4 /= np.linalg.norm(ideal4) + 1e-12
        ideal = np.abs(qa4u @ ideal4)
        mask &= (ideal >= float(ideal_min))
    # Optional: enable mod-9 closure gate here if desired (too strict for random floats)
    # mask &= mod9_closure_gate(b, e, d, a)
    if not np.any(mask):
        return np.array([], dtype=int), np.array([], dtype=np.float64)

    # Step 2: QA pre-ranking
    idx_pool = np.where(mask)[0]
    qe_scores = qa_rank(b[idx_pool], e[idx_pool], d[idx_pool], a[idx_pool], **(qe_kwargs or {}))
    order_qe = np.argsort(-qe_scores)
    idx_qe = idx_pool[order_qe[: min(qe_topk, order_qe.shape[0])]]

    # Step 3: E8 rerank
    vecs = build_e8_vectors(b[idx_qe], e[idx_qe], d[idx_qe], a[idx_qe])
    scores = e8_scores_auto(vecs, np.asarray(e8_roots), vec_chunk=e8_chunk)
    order_e8 = np.argsort(-scores)
    final_idx = idx_qe[order_e8[: min(topk, order_e8.shape[0])]]
    final_scores = scores[order_e8[: min(topk, order_e8.shape[0])]]
    return final_idx, final_scores


def _digital_root_py(v: float) -> int:
    n = int(v) if v >= 0 else 0
    if n == 0:
        return 9
    while n >= 10:
        s = 0
        t = n
        while t > 0:
            s += t % 10
            t //= 10
        n = s
    return n
