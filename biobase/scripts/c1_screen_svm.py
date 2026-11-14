#!/usr/bin/env python3
"""Exploratory comparison of max-margin classifiers on fixed slide features."""
import json
from pathlib import Path
import time

import numpy as np
from sklearn.svm import SVC

from c1_features import load_features, make_kernels


def main():
    root = Path(__file__).resolve().parents[1]
    slides, features, present = load_features(root, include_20x=True)
    kernels = make_kernels(features)
    classes = sorted({s["organGroup"] for s in slides if s.get("organGroup")})
    labels = np.array([classes.index(s["organGroup"]) if s.get("organGroup") else -1 for s in slides])
    indices = np.where((labels >= 0) & present["gigapath"])[0]
    selected = ["gigapath", "giga_clip_0.5", "giga_clip_0.75", "giga_hoptimus", "anchor_dinov2_quantiles", "anchor_20x_cls_0.25"]
    results = []
    start = time.monotonic()
    for name in selected:
        for regularization in [1., 10., 100.]:
            predictions = []
            for i in indices:
                train = indices[indices != i]
                model = SVC(C=regularization, kernel="precomputed")
                model.fit(kernels[name][np.ix_(train, train)], labels[train])
                predictions.append(int(model.predict(kernels[name][np.ix_([i], train)])[0]))
            result = {"kernel": name, "C": regularization, "loo_correct": int(np.sum(np.array(predictions) == labels[indices])), "total": len(indices)}
            results.append(result)
            print(json.dumps(result), flush=True)
    (root / "tmp/c1_improved/svm_screen.json").write_text(json.dumps(results, indent=2) + "\n")
    print(f"Elapsed {time.monotonic() - start:.1f}s", flush=True)


if __name__ == "__main__":
    main()
