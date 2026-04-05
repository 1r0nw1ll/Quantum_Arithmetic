#!/usr/bin/env python3
"""
qa_paper.py — Overleaf evidence pipeline wrapper

Runs the full QA evidence pipeline (bench → plots → LaTeX) and emits a JSON
summary that other agents (e.g., the Agent Builder) can consume.

Usage:
  python qa_agents/cli/qa_paper.py --run --json-out artifacts/overleaf/qa_paper.json

Outputs:
  artifacts/overleaf/
    - qa_training_compute_section.tex
    - qa_benchmarks.png
    - qa_pcn_theta_compare.png
    - qa_jepa_convergence.png
  artifacts/qa_overleaf_bundle.tar.gz
  (optional) JSON summary of results
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Dict, Any


# qa_paper.py lives at qa_lab/qa_agents/cli/qa_paper.py;
# the Makefile with the qa-* targets lives at qa_lab/Makefile
# (NOT the repo-root Makefile).  All `make ...` and relative path
# lookups must happen from qa_lab/, regardless of the caller's cwd.
_QA_LAB_DIR = Path(__file__).resolve().parent.parent.parent

BENCH_JSON = str(_QA_LAB_DIR / "target/qa_benchmarks/summary.json")
ARTIFACTS = [
    str(_QA_LAB_DIR / "artifacts/overleaf/qa_training_compute_section.tex"),
    str(_QA_LAB_DIR / "artifacts/qa_overleaf_bundle.tar.gz"),
    str(_QA_LAB_DIR / "plots/qa_benchmarks.png"),
    str(_QA_LAB_DIR / "plots/qa_pcn_theta_compare.png"),
    str(_QA_LAB_DIR / "plots/qa_jepa_convergence.png"),
]


def run_make(target: str) -> None:
    """Run a make target from qa_lab/, where the qa-* targets are defined."""
    subprocess.run(["make", target], check=True, cwd=str(_QA_LAB_DIR))


def load_bench_metrics(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r") as f:
            rows = json.load(f)
        # Aggregate last matching pair (SGD/HGD) or compute averages
        s_steps = [r["steps_to_tol"] for r in rows if r.get("method") == "SGD"]
        h_steps = [r["steps_to_tol"] for r in rows if r.get("method") == "HGD"]
        s_comp = [r.get("compute_units", 0) for r in rows if r.get("method") == "SGD"]
        h_comp = [r.get("compute_units", 0) for r in rows if r.get("method") == "HGD"]
        def mean(x):
            return (sum(x) / len(x)) if x else 0.0
        step_speedup = (mean(s_steps) / mean(h_steps)) if mean(h_steps) > 0 else 0.0
        compute_ratio = (mean(s_comp) / mean(h_comp)) if mean(h_comp) > 0 else 0.0
        return {
            "sgd_steps_mean": mean(s_steps),
            "hgd_steps_mean": mean(h_steps),
            "step_speedup": step_speedup,
            "compute_ratio": compute_ratio,
        }
    except Exception:
        return {}


def gather(ensure_exists: bool = True) -> Dict[str, Any]:
    summ = {
        "artifacts": [p for p in ARTIFACTS if (not ensure_exists) or os.path.exists(p)],
        "metrics": load_bench_metrics(BENCH_JSON),
    }
    # If a sweep was run (multiple (dim,lr) groups), compute wins/total + mean ratios
    try:
        with open(BENCH_JSON, "r") as f:
            rows = json.load(f)
        # Group by (dim, lr) string key
        by_cfg = {}
        for r in rows:
            key = (r.get("dim"), r.get("lr"))
            by_cfg.setdefault(key, []).append(r)
        wins = 0
        total = 0
        speedups = []
        computes = []
        for key, grp in by_cfg.items():
            s_steps = [g["steps_to_tol"] for g in grp if g.get("method") == "SGD"]
            h_steps = [g["steps_to_tol"] for g in grp if g.get("method") == "HGD"]
            s_comp = [g.get("compute_units", 0) for g in grp if g.get("method") == "SGD"]
            h_comp = [g.get("compute_units", 0) for g in grp if g.get("method") == "HGD"]
            if s_steps and h_steps:
                total += 1
                ms = sum(s_steps)/len(s_steps)
                mh = sum(h_steps)/len(h_steps)
                cs = (sum(s_comp)/len(s_comp)) if s_comp else 0.0
                ch = (sum(h_comp)/len(h_comp)) if h_comp else 0.0
                sp = (ms/mh) if mh>0 else 0.0
                cr = (cs/ch) if ch>0 else 0.0
                if sp > 1.0:
                    wins += 1
                speedups.append(sp)
                computes.append(cr)
        if total > 0:
            summ["sweep"] = {
                "wins": wins,
                "total": total,
                "mean_step_speedup": (sum(speedups)/len(speedups)) if speedups else 0.0,
                "mean_compute_ratio": (sum(computes)/len(computes)) if computes else 0.0,
            }
    except Exception:
        pass
    # Raman metrics (optional): parse raman CSV logs if present
    try:
        def _read_csv(path):
            import csv
            rows = []
            with open(path, newline="") as f:
                r = csv.DictReader(f)
                for row in r:
                    rows.append({k.strip().lower(): row[k] for k in row})
            return rows
        def _metrics(rows, target=0.90):
            best_acc = 0.0
            epochs_to_target = None
            for row in rows:
                e = int(row.get('epoch', 0) or 0)
                acc = float(row.get('acc', 0) or 0)
                if acc > best_acc:
                    best_acc = acc
                if epochs_to_target is None and acc >= target:
                    epochs_to_target = e
            return best_acc, epochs_to_target
        sgd_rows = _read_csv('target/qa_raman/raman_sgd.csv')
        hgd_rows = _read_csv('target/qa_raman/raman_hgd.csv')
        target_acc = float(os.getenv('QA_RAMAN_TARGET_ACC', '0.90'))
        s_best, s_ep = _metrics(sgd_rows, target_acc)
        h_best, h_ep = _metrics(hgd_rows, target_acc)
        summ['raman'] = {
            'target_acc': target_acc,
            'sgd_best_acc': s_best,
            'hgd_best_acc': h_best,
            'sgd_epochs_to_target': s_ep,
            'hgd_epochs_to_target': h_ep,
        }
    except Exception:
        pass
    return summ


def main():
    ap = argparse.ArgumentParser(description="Run QA paper pipeline and emit summary JSON")
    ap.add_argument("--run", action="store_true", help="Run the full pipeline (make qa-paper)")
    ap.add_argument("--json-out", default="", help="Optional JSON summary output path")
    ap.add_argument("--print", action="store_true", help="Print JSON summary to stdout")
    ap.add_argument("--min-step-speedup", type=float, default=None, help="Guardrail: minimum acceptable step speedup (SGD/HGD)")
    ap.add_argument("--min-compute-ratio", type=float, default=None, help="Guardrail: minimum acceptable compute ratio (SGD/HGD)")
    # Sweep options
    ap.add_argument("--sweep", action="store_true", help="Run a parameter sweep instead of the canonical single config")
    ap.add_argument("--dims", default="4,8,16,32", help="Comma-separated dims for sweep")
    ap.add_argument("--lrs", default="0.05,0.1,0.2", help="Comma-separated SGD LRs for sweep")
    ap.add_argument("--lrh-mult", type=float, default=2.0, help="HGD LR multiplier relative to SGD LR")
    ap.add_argument("--repeats", type=int, default=3, help="Repeats per sweep configuration")
    ap.add_argument("--tol", type=float, default=1e-10, help="Tolerance for convergence")
    ap.add_argument("--max-steps", type=int, default=2000, help="Max steps per run")
    ap.add_argument("--hgd-gain", type=float, default=1.8, help="HGD mask gain")
    ap.add_argument("--hgd-floor", type=float, default=0.3, help="HGD mask floor")
    args = ap.parse_args()

    if args.run:
        if args.sweep:
            # clean previous summaries
            try:
                os.remove("target/qa_benchmarks/summary.csv")
            except Exception:
                pass
            try:
                os.remove("target/qa_benchmarks/summary.json")
            except Exception:
                pass
            dims = [int(x) for x in args.dims.split(',') if x]
            lrs = [float(x) for x in args.lrs.split(',') if x]
            # run grid
            for d in dims:
                for lr in lrs:
                    lrh = lr * args.lrh_mult
                    cmd = [
                        "cargo", "run", "--release", "--bin", "qa_speed_benchmark", "--",
                        "--dim", str(d), "--lr", str(lr), "--lr-hgd", str(lrh),
                        "--tol", str(args.tol), "--max-steps", str(args.max_steps),
                        "--repeats", str(args.repeats), "--hgd-gain", str(args.hgd_gain), "--hgd-floor", str(args.hgd_floor)
                    ]
                    subprocess.run(cmd, check=True)
            # generate plots and LaTeX from the accumulated summary
            os.makedirs("plots", exist_ok=True)
            subprocess.run(["python3", "scripts/qa_plot_benchmarks.py", "--csv", "target/qa_benchmarks/summary.csv", "--out", "plots/qa_benchmarks.png"], check=True)
            subprocess.run(["cargo", "run", "--release", "--bin", "qa_theory_export"], check=True)
            # bundle
            run_make("qa-paper-bundle")
        else:
            run_make("qa-paper")

    summary = gather(ensure_exists=True)
    # Flatten key metrics for simpler acceptance checks by agents
    metrics = summary.get("metrics", {})
    summary["step_speedup"] = metrics.get("step_speedup", 0.0)
    summary["compute_ratio"] = metrics.get("compute_ratio", 0.0)

    # Guardrails: fail if thresholds are provided and not met (canonical metrics)
    if args.min_step_speedup is not None and summary["step_speedup"] < args.min_step_speedup:
        raise SystemExit(
            f"Regression: QA step speedup too small (got {summary['step_speedup']:.2f} < {args.min_step_speedup:.2f})"
        )

    # Soft Raman guardrail: warn if HGD did not reach target accuracy faster
    try:
        r = summary.get("raman", {})
        s_ep = r.get("sgd_epochs_to_target")
        h_ep = r.get("hgd_epochs_to_target")
        if s_ep is not None and h_ep is not None and h_ep >= s_ep:
            print("[WARN] Raman guardrail not met: HGD did not reach target accuracy faster than SGD.")
    except Exception:
        pass
    if args.min_compute_ratio is not None and summary["compute_ratio"] < args.min_compute_ratio:
        raise SystemExit(
            f"Regression: QA compute ratio too small (got {summary['compute_ratio']:.2f} < {args.min_compute_ratio:.2f})"
        )
    if args.json_out:
        os.makedirs(os.path.dirname(args.json_out) or ".", exist_ok=True)
        with open(args.json_out, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"Wrote: {args.json_out}")
    if args.print or not args.json_out:
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
