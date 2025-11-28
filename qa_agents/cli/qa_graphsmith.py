"""
Auto-refactor: normalize formatting for qa_graphsmith.py
"""

#!/usr/bin/env python3
"""
QA Graphsmith v1.0
Generates lightweight visualizations/summaries for the QA Lab.

Design:
- Tries to use matplotlib and networkx if available.
- Falls back to plain-text summaries when optional deps are missing.
"""

from pathlib import Path
import json
import sys
from datetime import datetime


BASE_DIR = Path(__file__).parent.parent.parent
PLOTS_DIR = BASE_DIR / "artifacts" / "plots"
PLOTS_DIR.mkdir(parents=True, exist_ok=True)


def load_qa_dataset(path: Path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
            # QA dataset layout
            total = sum(len(v) for v in data["data"].values())
            return {"type": "qa", "total": total, "groups": {k: len(v) for k, v in data["data"].items()}}
        elif isinstance(data, dict) and "texts" in data:
            return {"type": "lm", "total": len(data["texts"]) }
    except Exception:
        pass
    return {"type": "none", "total": 0}


def try_matplotlib_plot(summary: dict) -> bool:
    try:
        import matplotlib
        matplotlib.use("Agg")  # headless backend
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        return False

    fig = plt.figure(figsize=(8, 4))
    fig.suptitle("QA Lab Dataset Summary")

    # Bar for QA dataset groups (if present)
    if summary.get("type") == "qa" and summary.get("groups"):
        ax = fig.add_subplot(1, 2, 1)
        groups = list(summary["groups"].keys())
        counts = [summary["groups"][g] for g in groups]
        ax.bar(groups, counts, color="#4C78A8")
        ax.set_title("QA groups")
        ax.set_ylabel("samples")
        ax.tick_params(axis='x', rotation=45)

    # Overall totals
    ax2 = fig.add_subplot(1, 2, 2)
    labels = ["QA", "LM"]
    values = [summary.get("qa_total", 0), summary.get("lm_total", 0)]
    ax2.bar(labels, values, color="#F58518")
    ax2.set_title("Totals")
    for i, v in enumerate(values):
        ax2.text(i, v + max(values) * 0.02 if max(values) else 0.1, str(v), ha='center')

    fig.tight_layout()
    out_png = PLOTS_DIR / "qa_dataset_summary.png"
    fig.savefig(out_png, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved visualization: {out_png}")
    return True


def try_networkx_workflow() -> bool:
    try:
        import networkx as nx  # type: ignore
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        return False

    g = nx.DiGraph()
    steps = ["scout", "prioritize", "plan", "dispatch", "review", "archive"]
    for i in range(len(steps) - 1):
        g.add_edge(steps[i], steps[i + 1])

    pos = nx.spring_layout(g, seed=42)
    plt.figure(figsize=(6, 4))
    nx.draw_networkx_nodes(g, pos, node_color="#72B7B2")
    nx.draw_networkx_edges(g, pos, arrows=True, arrowstyle='-|>', arrowsize=15)
    nx.draw_networkx_labels(g, pos)
    plt.axis("off")
    out_png = PLOTS_DIR / "agent_workflow.png"
    plt.savefig(out_png, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved visualization: {out_png}")
    return True


def write_text_summary(summary: dict):
    out_txt = PLOTS_DIR / "qa_dataset_summary.txt"
    lines = [f"QA Graphsmith Report @ {datetime.now().isoformat()}"]
    lines.append("")
    lines.append(f"QA dataset items: {summary.get('qa_total', 0)}")
    if summary.get("type") == "qa" and summary.get("groups"):
        for k, v in summary["groups"].items():
            lines.append(f"  - {k}: {v}")
    lines.append(f"LM dataset items: {summary.get('lm_total', 0)}")
    out_txt.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved summary: {out_txt}")


def main() -> int:
    qa_json = BASE_DIR / "qa_data" / "qa_training_dataset.json"
    lm_json = BASE_DIR / "wikitext_train_small.json"

    qa_summary = load_qa_dataset(qa_json)
    lm_summary = load_qa_dataset(lm_json)

    summary = {
        "qa_total": qa_summary.get("total", 0),
        "lm_total": lm_summary.get("total", 0),
    }
    if qa_summary.get("groups"):
        summary["type"] = "qa"
        summary["groups"] = qa_summary["groups"]

    plotted = try_matplotlib_plot(summary)
    workflow = try_networkx_workflow()

    if not plotted:
        write_text_summary(summary)

    if not workflow:
        # Provide a minimal DOT file to visualize later
        dot_path = PLOTS_DIR / "agent_workflow.dot"
        dot = "digraph G { scout -> prioritize -> plan -> dispatch -> review -> archive }\n"
        dot_path.write_text(dot, encoding="utf-8")
        print(f"Saved DOT workflow: {dot_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
