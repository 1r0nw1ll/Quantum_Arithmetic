#!/usr/bin/env python3
import argparse
import csv
import os
import matplotlib.pyplot as plt


def read_log(path):
    epochs, loss, acc = [], [], []
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            epochs.append(int(row["epoch"]))
            loss.append(float(row["loss"]))
            acc.append(float(row["acc"]))
    return epochs, loss, acc


def main():
    ap = argparse.ArgumentParser(description="Plot Raman classification accuracy (SGD vs HGD)")
    ap.add_argument("--csv-sgd", required=True)
    ap.add_argument("--csv-hgd", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    es, ls, as_ = read_log(args.csv_sgd)
    eh, lh, ah = read_log(args.csv_hgd)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7, 6), constrained_layout=True)
    ax1.plot(es, as_, label="SGD", color="#6baed6")
    ax1.plot(eh, ah, label="HGD", color="#31a354")
    ax1.set_xlabel("epoch")
    ax1.set_ylabel("accuracy")
    ax1.set_title("Raman classification: accuracy vs epoch")
    ax1.legend()

    ax2.plot(es, ls, label="SGD", color="#9ecae1")
    ax2.plot(eh, lh, label="HGD", color="#74c476")
    ax2.set_xlabel("epoch")
    ax2.set_ylabel("loss")
    ax2.set_title("Raman classification: loss vs epoch")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    fig.savefig(args.out, dpi=150)
    print(f"Wrote: {args.out}")


if __name__ == "__main__":
    main()

