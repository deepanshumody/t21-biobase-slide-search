#!/usr/bin/env python3
"""Exploratory screen; scores are used for development, not independent reporting."""
import argparse
import json
from pathlib import Path

import numpy as np

from c1_embeddings import folds
from c1_features import load_features, make_kernels


def ridge_loo(kernel, targets, indices, alphas):
    eigenvalues, eigenvectors = np.linalg.eigh(kernel[np.ix_(indices, indices)])
    projected = eigenvectors.T @ targets[indices]
    result = []
    for alpha in alphas:
        reciprocal = 1 / (np.maximum(eigenvalues, 0) + alpha)
        coefficients = (eigenvectors * reciprocal) @ projected
        inverse_diagonal = (eigenvectors ** 2) @ reciprocal
        result.append(targets[indices] - coefficients / inverse_diagonal[:, None])
    return result


def ridge_fit(kernel, targets, train, query, alpha):
    coefficients = np.linalg.solve(kernel[np.ix_(train, train)] + alpha * np.eye(len(train)), targets[train])
    return kernel[np.ix_(query, train)] @ coefficients


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-20x", action="store_true")
    parser.add_argument("--include-overview", action="store_true")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    slides, features, present = load_features(args.root, args.include_20x, args.include_overview)
    kernels = make_kernels(features)
    classes = sorted({s["organGroup"] for s in slides if s.get("organGroup") and not s.get("heldout")})
    labels = np.array([classes.index(s["organGroup"]) if s.get("organGroup") and not s.get("heldout") else -1 for s in slides])
    targets = np.eye(len(classes))[np.maximum(labels, 0)]
    # Exact common cohort and order used by the original 188-slide experiment.
    indices = np.where((labels >= 0) & present["gigapath"])[0]
    alphas = [0.003, 0.01, 0.03, 0.1, 0.3, 1.]
    rows = []
    for name, kernel in kernels.items():
        for alpha, scores in zip(alphas, ridge_loo(kernel, targets, indices, alphas)):
            rows.append({"kernel": name, "alpha": alpha, "correct": int(np.sum(scores.argmax(axis=1) == labels[indices])),
                         "loo_accuracy": float(np.mean(scores.argmax(axis=1) == labels[indices]))})
    rows.sort(key=lambda r: (-r["correct"], r["kernel"], r["alpha"]))
    print('Exploratory LOO top candidates:', flush=True)
    for row in rows[:20]:
        print(json.dumps(row), flush=True)
    suffix = ("_20x" if args.include_20x else "") + ("_overview" if args.include_overview else "")
    out = args.root / "tmp/c1_improved" / ("screen" + suffix + ".json")
    out.write_text(json.dumps(rows, indent=2) + "\n")
    # Development-only split comparison. Confirmatory splits use other seeds.
    selected_names = list(dict.fromkeys(r["kernel"] for r in rows))[:6]
    selected_names += ["giga_clip_0.5"]
    for name in dict.fromkeys(selected_names):
        predictions = np.zeros((len(slides), len(classes)))
        for validation in folds(indices, labels, 17):
            train = np.setdiff1d(indices, validation)
            inner = ridge_loo(kernels[name], targets, train, alphas)
            best = int(np.argmax([np.mean(s.argmax(axis=1) == labels[train]) for s in inner]))
            predictions[validation] = ridge_fit(kernels[name], targets, train, validation, alphas[best])
        print('Development outer fold', name, float(np.mean(predictions[indices].argmax(axis=1) == labels[indices])), flush=True)


if __name__ == "__main__":
    main()
