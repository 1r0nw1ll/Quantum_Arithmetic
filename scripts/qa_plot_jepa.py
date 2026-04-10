"""
Auto-refactor: normalize formatting for qa_plot_jepa.py
"""

#!/usr/bin/env python3
import argparse
import csv
import os
import matplotlib.pyplot as plt


def read_log(path):
    epochs, avg = [], []
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            epochs.append(int(row["epoch"]))
            avg.append(float(row["avg_energy"]))
    return epochs, avg


def main():
    ap = argparse.ArgumentParser(description="Plot JEPA convergence (SGD vs HGD)")
    ap.add_argument("--csv-sgd", required=True)
    ap.add_argument("--csv-hgd", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    es, ys = read_log(args.csv_sgd)
    eh, yh = read_log(args.csv_hgd)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(es, ys, label="SGD", color="#6baed6")
    ax.plot(eh, yh, label="HGD", color="#31a354")
    ax.set_xlabel("epoch")
    ax.set_ylabel("avg energy")
    ax.set_title("JEPA convergence")
    ax.legend()

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    fig.savefig(args.out, dpi=150)
    print(f"Wrote: {args.out}")


if __name__ == "__main__":
    main()

