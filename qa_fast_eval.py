#!/usr/bin/env python3
"""
qa_fast_eval.py - One-button fast-path evaluation runner for QA Lab.

Runs a focused evaluation of the fast-prune pipeline (gates → QE → E8) and records
timings and kept ratios. Generates E8 roots if none are found (simplified default).

Outputs:
  - artifacts/evals/fastpath_eval.json: timings and parameters
  - artifacts/evals/fastpath_eval.txt: human-readable summary
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from datetime import datetime, timezone
import numpy as np

from qa_fastpath import (
    get_e8_roots,
    fast_prune_and_rank,
    mod24_gate, digital_root_gate, closure_gate, inner_ellipse_gate, triangle_gate,
    qa_rank, build_e8_vectors, e8_scores_auto, harmonic_index,
)
try:
    from qa_ebm_cert_lane import emit_fastpath_case_certs
except Exception:
    emit_fastpath_case_certs = None
try:
    import qa_lab_rs as _rs  # Rust kernels for QA Bell tests
except Exception:
    _rs = None


def _ensure_dirs():
    Path('artifacts/evals').mkdir(parents=True, exist_ok=True)


def _load_dotenv_into_environ(dotenv_path: Path = Path('.env')) -> None:
    """Load KEY=VALUE pairs from .env into os.environ (best-effort)."""
    try:
        if not dotenv_path.exists():
            return
        text = dotenv_path.read_text(encoding='utf-8', errors='ignore')
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            key, val = line.split('=', 1)
            key = key.strip(); val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
    except Exception:
        pass


def _load_or_create_roots() -> np.ndarray:
    roots_info = get_e8_roots()
    if roots_info:
        roots, _ = roots_info
        return roots
    # Try generating canonical 240 E8 roots
    gen_script = Path('qa_lab/scripts/generate_e8_roots.py')
    if gen_script.exists():
        try:
            import subprocess
            subprocess.run(['python3', str(gen_script)], check=False)
            roots_info2 = get_e8_roots()
            if roots_info2:
                roots, _ = roots_info2
                return roots
        except Exception:
            pass
    # Fallback: generate simplified unit roots (ideal root + axis-aligned)
    ideal = np.array([1, 1, 2, 3, 0, 0, 0, 0], dtype=np.float64)
    ideal /= np.linalg.norm(ideal) + 1e-12
    axes = np.eye(8, dtype=np.float64)
    roots = np.vstack([ideal.reshape(1, -1), axes])
    outp = Path('qa_lab/data'); outp.mkdir(parents=True, exist_ok=True)
    np.save(outp / 'e8_roots_unit.npy', roots)
    return roots


def _run_eval(n: int, qe_topk: int, topk: int, seed: int = 0,
              mod24_allowed=(1,5,7,11), dr_allowed=(1,3,9),
              closure_tol=1e-9, inner_tol=1e-9, triangle_tol=1e-9,
              family_phi_tol: float | None = 0.05,
              e8_chunk: int | None = None,
              qe_curv_weight: float | None = None,
              prefer_numpy: bool | None = None,
              disable_rust: bool | None = None,
              *,
              baseline_only: bool = False,
              baseline_override_sec: float | None = None) -> dict:
    # Set env flags
    if qe_curv_weight is not None:
        os.environ['QA_QE_CURV_WEIGHT'] = str(qe_curv_weight)
    if prefer_numpy is not None:
        os.environ['QA_E8_PREFER_NUMPY'] = '1' if prefer_numpy else '0'
    if disable_rust is not None:
        os.environ['QA_E8_DISABLE_RUST'] = '1' if disable_rust else '0'
    if e8_chunk is not None:
        os.environ['QA_E8_VEC_CHUNK'] = str(int(e8_chunk))

    rng = np.random.default_rng(seed)
    b = rng.random(n).astype(np.float64)
    e = rng.random(n).astype(np.float64)
    d = (b + e).astype(np.float64)
    a = (e + d).astype(np.float64)

    roots_raw = _load_or_create_roots()
    # Use a heavier root set for fair baseline timing if needed (tile to 240)
    roots = roots_raw
    roots_source = 'provided'
    if roots.shape[0] < 100:
        reps = int(np.ceil(240 / roots.shape[0]))
        roots = np.tile(roots, (reps, 1))[:240]
        roots_source = f'tiled_{roots_raw.shape[0]}_to_{roots.shape[0]}'

    # Baseline: NumPy-only E8 rerank over full set (no pruning)
    # Allow override via baseline_override_sec to skip computing it here.
    vecs_full = build_e8_vectors(b, e, d, a)
    if baseline_override_sec is not None:
        tb0 = 0.0
        tb1 = float(baseline_override_sec)
        baseline_idx = None
    else:
        prev_np = os.environ.get('QA_E8_PREFER_NUMPY')
        prev_dis = os.environ.get('QA_E8_DISABLE_RUST')
        os.environ['QA_E8_PREFER_NUMPY'] = '1'
        os.environ['QA_E8_DISABLE_RUST'] = '1'
        try:
            tb0 = time.perf_counter()
            scores_full = e8_scores_auto(vecs_full, roots, vec_chunk=e8_chunk)
            order_full = np.argsort(-scores_full)
            baseline_idx = order_full[:topk]
            tb1 = time.perf_counter()
        finally:
            # Restore original backend preferences
            if prev_np is None:
                os.environ.pop('QA_E8_PREFER_NUMPY', None)
            else:
                os.environ['QA_E8_PREFER_NUMPY'] = prev_np
            if prev_dis is None:
                os.environ.pop('QA_E8_DISABLE_RUST', None)
            else:
                os.environ['QA_E8_DISABLE_RUST'] = prev_dis

    if baseline_only:
        return {
            'n': n,
            'qe_topk': qe_topk,
            'qa_topk': qe_topk,
            'topk': topk,
            'kept': None,
            'post_gates': None,
            'post_qe': None,
            'post_qa': None,
            'kept_ratio': None,
            'time_sec_pipeline': None,
            'time_sec_baseline': tb1 - tb0,
            'speedup_vs_baseline': None,
            'roots_used': int(roots.shape[0]),
            'roots_source': roots_source,
        }

    # Fast pipeline: gates → QE → E8
    # Respect env override for family tolerance if provided
    try:
        fam_env = os.getenv('QA_FP_FAMILY_TOL')
        if fam_env is not None:
            family_phi_tol = float(fam_env)
    except Exception:
        pass
    t0 = time.perf_counter()
    # Optional quick ideal gate from env
    ideal_min_env = os.getenv('QA_FP_IDEAL_MIN')
    try:
        ideal_min = float(ideal_min_env) if ideal_min_env is not None else None
    except Exception:
        ideal_min = None

    idx, scores = fast_prune_and_rank(
        b, e, d, a, roots,
        mod24_allowed=mod24_allowed,
        dr_allowed=dr_allowed,
        closure_tol=closure_tol,
        inner_tol=inner_tol,
        wheel_allowed=(1,5,7,11),
        family_phi_tol=family_phi_tol,
        ideal_min=ideal_min,
        qe_topk=qe_topk,
        topk=topk,
        e8_chunk=e8_chunk,
        qe_kwargs=None,
        triangle_tol=triangle_tol,
        )
    t1 = time.perf_counter()

    kept = int(idx.shape[0])
    # Diagnostics: post-gates and post-QE survivors
    mg = mod24_gate(d, mod24_allowed)
    dg = digital_root_gate(a, dr_allowed)
    cg = closure_gate(b, e, d, a, tol=closure_tol) if closure_tol is not None else np.ones_like(d, dtype=bool)
    ig = inner_ellipse_gate(b, e, d, a, tol=inner_tol) if inner_tol is not None else np.ones_like(d, dtype=bool)
    tg = triangle_gate(b, e, d, a, tol=triangle_tol) if triangle_tol is not None else np.ones_like(d, dtype=bool)
    # Include wheel and mod-9 closure gates in diagnostics
    wg = mod24_gate(d, (1,5,7,11)) & mod24_gate(a, (1,5,7,11))
    if family_phi_tol is not None:
        # family gate: approximate via a/d and e/b checks
        phi = 1.6180339887498948
        err_ad = np.abs((a / (np.abs(d)+1e-12)) - phi)
        err_eb = np.abs((e / (np.abs(b)+1e-12)) - (phi - 1.0))
        fg = (err_ad <= family_phi_tol) | (err_eb <= family_phi_tol)
    else:
        fg = np.ones_like(d, dtype=bool)
    mask_gates = mg & dg & cg & ig & tg & wg & fg
    post_gates = int(mask_gates.sum())
    if post_gates > 0:
        qe_scores = qa_rank(b[mask_gates], e[mask_gates], d[mask_gates], a[mask_gates])
        order_qe = np.argsort(-qe_scores)
        post_qe = min(qe_topk, order_qe.shape[0])
    else:
        post_qe = 0

    # Optional: compute a small-sample Harmonic Index summary
    hi_mean_sample = None
    try:
        m = min(100_000, n)
        if m > 0:
            b_s, e_s, d_s, a_s = b[:m], e[:m], d[:m], a[:m]
            vecs_s = build_e8_vectors(b_s, e_s, d_s, a_s)
            e8_s = e8_scores_auto(vecs_s, roots, vec_chunk=e8_chunk)
            c = 2.0 * e_s * d_s
            f = b_s * a_s
            g = e_s * e_s + d_s * d_s
            loss_s = np.abs(c*c + f*f - g*g)
            hi_s = harmonic_index(e8_s, loss_s, k=0.25)
            hi_mean_sample = float(np.mean(hi_s))
    except Exception:
        hi_mean_sample = None

    res = {
        'n': n,
        'qe_topk': qe_topk,
        'qa_topk': qe_topk,
        'topk': topk,
        'kept': kept,
        'post_gates': post_gates,
        'post_qe': post_qe,
        'post_qa': post_qe,
        'kept_ratio': kept / max(1, n),
        'time_sec_pipeline': t1 - t0,
        'time_sec_baseline': tb1 - tb0,
        'speedup_vs_baseline': (tb1 - tb0) / max(1e-12, (t1 - t0)),
        'roots_used': int(roots.shape[0]),
        'roots_source': roots_source,
        'hi_mean_sample': hi_mean_sample,
        'selected_indices_sample': [int(v) for v in idx[: min(16, idx.shape[0])]],
        'selected_scores_sample': [float(v) for v in scores[: min(16, scores.shape[0])]],
        'env': {
            'QA_QE_CURV_WEIGHT': os.getenv('QA_QE_CURV_WEIGHT', ''),
            'QA_QA_CURV_WEIGHT': os.getenv('QA_QA_CURV_WEIGHT', ''),
            'QA_E8_PREFER_NUMPY': os.getenv('QA_E8_PREFER_NUMPY', ''),
            'QA_E8_DISABLE_RUST': os.getenv('QA_E8_DISABLE_RUST', ''),
            'QA_E8_VEC_CHUNK': os.getenv('QA_E8_VEC_CHUNK', ''),
            'QA_QE_IDEAL_WEIGHT': os.getenv('QA_QE_IDEAL_WEIGHT', ''),
            'QA_QA_IDEAL_WEIGHT': os.getenv('QA_QA_IDEAL_WEIGHT', ''),
        }
    }
    return res


def main():
    _ensure_dirs()
    _load_dotenv_into_environ(Path('.env'))
    results: dict[str, dict] = {}
    emit_ebm_certs = os.getenv('QA_EMIT_EBM_CERTS', '0') == '1'
    accept_by_verifier = os.getenv('QA_EBM_ACCEPT_BY_VERIFIER', '0') == '1'
    validate_emitted = os.getenv('QA_VALIDATE_EBM_CERTS', '1') != '0'
    ebm_run_id = os.getenv('QA_EBM_CERT_RUN_ID')
    if not ebm_run_id:
        ebm_run_id = datetime.now(timezone.utc).strftime("fastpath-%Y%m%d-%H%M%S")

    # If requested, compute NumPy-only baseline and exit (used by numpy-baseline target)
    if os.getenv('QA_SAVE_BASELINE_ONLY', '0') == '1':
        try:
            eval_n = int(os.getenv('QA_EVAL_N', '800000'))
        except Exception:
            eval_n = 800_000
        try:
            eval_qe = int(os.getenv('QA_EVAL_QE_TOPK', '1024'))
        except Exception:
            eval_qe = 1024
        base = _run_eval(n=eval_n, qe_topk=eval_qe, topk=256, seed=0,
                         qe_curv_weight=0.25, e8_chunk=200_000,
                         closure_tol=None, inner_tol=None, triangle_tol=None, family_phi_tol=None,
                         baseline_only=True)
        outp = Path('artifacts/evals/fastpath_baseline_np.json')
        outp.parent.mkdir(parents=True, exist_ok=True)
        with open(outp, 'w') as f:
            json.dump({
                'n': base['n'],
                'qe_topk': base['qe_topk'],
                'topk': base['topk'],
                'roots_used': base['roots_used'],
                'time_sec_baseline': base['time_sec_baseline'],
            }, f, indent=2)
        return

    # Optional external baseline override path
    baseline_override = None
    base_path = os.getenv('QA_USE_BASELINE_FROM')
    if base_path:
        try:
            data = json.loads(Path(base_path).read_text())
            baseline_override = float(data.get('time_sec_baseline'))
        except Exception:
            baseline_override = None

    # Default evaluation
    # Tuned defaults for clearer speedup vs NumPy baseline; allow env overrides
    # QA_EVAL_N and QA_EVAL_QE_TOPK to test larger N or leaner QE.
    try:
        eval_n = int(os.getenv('QA_EVAL_N', '800000'))
    except Exception:
        eval_n = 800_000
    try:
        eval_qe = int(os.getenv('QA_EVAL_QE_TOPK', '1024'))
    except Exception:
        eval_qe = 1024
    results['default'] = _run_eval(
        n=eval_n, qe_topk=eval_qe, topk=256, seed=0,
        qe_curv_weight=0.25, e8_chunk=200_000,
        closure_tol=None, inner_tol=None, triangle_tol=None, family_phi_tol=None,
        baseline_only=False, baseline_override_sec=baseline_override,
    )

    # NumPy-preferred path
    results['numpy_pref'] = _run_eval(n=200_000, qe_topk=4096, topk=256, seed=1,
                                      qe_curv_weight=0.25, e8_chunk=200_000,
                                      prefer_numpy=True)

    # Rust-disabled path
    results['rust_disabled'] = _run_eval(n=200_000, qe_topk=4096, topk=256, seed=2,
                                         qe_curv_weight=0.25, e8_chunk=200_000,
                                         disable_rust=True)

    summary_txt = []
    for k, v in results.items():
        summary_txt.append(
            f"[{k}] kept={v['kept']}/{v['n']} gates={v['post_gates']} qe={v['post_qe']} "
            f"time(pipeline)={v['time_sec_pipeline']:.3f}s baseline={v['time_sec_baseline']:.3f}s "
            f"speedup={v['speedup_vs_baseline']:.2f}x"
        )

    # Persist
    if emit_ebm_certs and emit_fastpath_case_certs is not None:
        cert_status: dict[str, dict] = {}
        for case_name in ("default", "numpy_pref", "rust_disabled"):
            case = results.get(case_name, {})
            cert_status[case_name] = emit_fastpath_case_certs(
                run_id=ebm_run_id,
                case_name=case_name,
                selected_indices=case.get('selected_indices_sample', []),
                selected_scores=case.get('selected_scores_sample', []),
                accepted_by_verifier=accept_by_verifier,
                validate=validate_emitted,
            )
        accepted_all = bool(accept_by_verifier) and all(
            isinstance(v, dict) and v.get("accepted_by_verifier") is True and v.get("ok") is True
            for v in cert_status.values()
        )
        results['ebm_certs'] = {
            'enabled': True,
            'run_id': ebm_run_id,
            'requested_verifier_bridge': accept_by_verifier,
            'accepted_by_verifier': accepted_all,
            'cases': cert_status,
        }
    elif emit_ebm_certs:
        results['ebm_certs'] = {
            'enabled': False,
            'error': 'qa_ebm_cert_lane_import_failed',
        }

    with open('artifacts/evals/fastpath_eval.json', 'w') as f:
        json.dump(results, f, indent=2)
    with open('artifacts/evals/fastpath_eval.txt', 'w') as f:
        f.write('\n'.join(summary_txt) + '\n')

    # Quantum verification benchmarks (if Rust kernels available)
    try:
        if _rs is not None:
            N = 24
            # Discrete grid search for CHSH on N=24: fix a0=0, scan a1,b0,b1
            best_s = 0.0
            best_abs = -1.0
            best = (0, 0, 0, 0)
            a0 = 0
            for a1 in range(N):
                for b0 in range(N):
                    for b1 in range(N):
                        s = float(_rs.compute_chsh_qa(N, a0, a1, b0, b1))
                        if abs(s) > best_abs:
                            best_s = s
                            best_abs = abs(s)
                            best = (a0, a1, b0, b1)
            chsh_s = best_s
            # I3322 discrete search on small candidate sets (fast, robust)
            def wrap(idx: int) -> int:
                return int(idx % N)
            a_cand = [
                (0, N//4, N//2),
                (0, wrap(N//4-1), N//2),
                (0, wrap(N//4+1), N//2),
                (0, N//4, wrap(N//2-1)),
                (0, N//4, wrap(N//2+1)),
            ]
            b_base = (N//8, 3*N//8, 5*N//8)
            k_variants = [-1, 0, 1]
            best_i = -1e18
            best_i_idx = (0,0,0,0,0,0)
            for a1,a2,a3 in a_cand:
                for k1 in k_variants:
                    for k2 in k_variants:
                        for k3 in k_variants:
                            b1 = wrap(b_base[0]+k1); b2 = wrap(b_base[1]+k2); b3 = wrap(b_base[2]+k3)
                            val = float(_rs.compute_i3322_qa(N, a1,a2,a3, b1,b2,b3))
                            if val > best_i:
                                best_i = val
                                best_i_idx = (a1,a2,a3,b1,b2,b3)
            results['quantum'] = {
                'CHSH': {
                    'N': N, 'S': chsh_s, 'tsirelson': 2.8284271247461903,
                    'best_indices': {'a0': best[0], 'a1': best[1], 'b0': best[2], 'b1': best[3]}
                },
                'I3322': {
                    'N': N, 'value': best_i,
                    'best_indices': {
                        'a1': best_i_idx[0], 'a2': best_i_idx[1], 'a3': best_i_idx[2],
                        'b1': best_i_idx[3], 'b2': best_i_idx[4], 'b3': best_i_idx[5],
                    }
                },
                'polyhedra': {
                    'octahedron': float(_rs.bell_octahedron_qa(N)),
                    'icosahedron': float(_rs.bell_icosahedron_qa(N)),
                    'dodecahedron': float(_rs.bell_dodecahedron_qa(N)),
                }
            }
            with open('artifacts/evals/fastpath_eval.json', 'w') as f:
                json.dump(results, f, indent=2)
            with open('artifacts/evals/fastpath_eval.txt', 'a') as f:
                a0,besta1,bestb0,bestb1 = best
                f.write(f"CHSH(N={N}): max|S|={abs(chsh_s):.4f} (<= 2.8284) at a0={a0},a1={besta1},b0={bestb0},b1={bestb1}\n")
                f.write(
                    "I3322(N={N}): value={val:.4f} at a=({a1},{a2},{a3}), b=({b1},{b2},{b3})\n".format(
                        N=N, val=best_i,
                        a1=best_i_idx[0], a2=best_i_idx[1], a3=best_i_idx[2],
                        b1=best_i_idx[3], b2=best_i_idx[4], b3=best_i_idx[5],
                    )
                )
    except Exception:
        pass


if __name__ == '__main__':
    main()
