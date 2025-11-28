#!/usr/bin/env python3
import argparse
import csv
import os
import matplotlib.pyplot as plt


def read_series(path):
    steps, energy, lmin, lmax = [], [], [], []
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            steps.append(int(row["step"]))
            energy.append(float(row["energy"]))
            lmin.append(float(row.get("lambda_min", 0.0) or 0.0))
            lmax.append(float(row.get("lambda_max", 0.0) or 0.0))
    return steps, energy, lmin, lmax


def main():
    ap = argparse.ArgumentParser(description="Plot PCN energy vs step for theta=0 vs theta=pi")
    ap.add_argument("--csv-theta-0", required=True)
    ap.add_argument("--csv-theta-pi", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    s0, e0, _, _ = read_series(args.csv_theta_0)
    spi, epi, _, _ = read_series(args.csv_theta_pi)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(s0, e0, label="theta=0", color="#3182bd")
    ax.plot(spi, epi, label="theta=pi", color="#e34a33")
    ax.set_xlabel("step")
    ax.set_ylabel("energy")
    ax.set_title("PCN energy vs step")
    ax.legend()

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    fig.savefig(args.out, dpi=150)
    print(f"Wrote: {args.out}")


if __name__ == "__main__":
    main()

