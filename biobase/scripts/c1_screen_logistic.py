#!/usr/bin/env python3
"""Development-only multinomial logistic probes on fixed image kernels."""
import json
from pathlib import Path
import time
import warnings

import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression

from c1_features import load_features, make_kernels


def main():
    warnings.simplefilter("error", ConvergenceWarning)
    root = Path(__file__).resolve().parents[1]
    slides, features, present = load_features(root)
    kernels = make_kernels(features)
    classes = sorted({s["organGroup"] for s in slides if s.get("organGroup")})
    labels = np.array([classes.index(s["organGroup"]) if s.get("organGroup") else -1 for s in slides])
    indices = np.where((labels >= 0) & present["gigapath"])[0]
    results = []
    start = time.monotonic()
    for name in ["gigapath", "giga_clip_0.5", "anchor_dinov2_quantiles"]:
        # An exact finite feature map of the fixed kernel, with no fitted labels.
        values, vectors = np.linalg.eigh(kernels[name])
        matrix = vectors * np.sqrt(np.maximum(values, 0))
        for regularization in [10., 100., 1000.]:
            predictions = []
            for i in indices:
                train = indices[indices != i]
                model = LogisticRegression(C=regularization, max_iter=2000, tol=1e-5)
                model.fit(matrix[train], labels[train])
                predictions.append(int(model.predict(matrix[[i]])[0]))
            result = {"kernel": name, "C": regularization, "loo_correct": int(np.sum(np.array(predictions) == labels[indices])), "total": len(indices)}
            results.append(result)
            print(json.dumps(result), flush=True)
    (root / "tmp/c1_improved/logistic_screen.json").write_text(json.dumps(results, indent=2) + "\n")
    print(f"Elapsed {time.monotonic() - start:.1f}s", flush=True)


if __name__ == "__main__":
    main()
