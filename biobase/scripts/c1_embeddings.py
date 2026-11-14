#!/usr/bin/env python3
"""Benchmark supplied C1 embeddings and write a provisional submission.

Requires NumPy. No held-out labels, reports, filenames, or supplier metadata
are used as predictive features. Run from any directory with --root if needed.
"""
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

try:
    import numpy as np
except ImportError as error:
    raise SystemExit("NumPy is required. Install it with: python3 -m pip install numpy") from error


def write_csv(path, fields, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def folds(indices, labels, seed):
    """Three slide-level folds, keeping both examples of rare classes apart."""
    rng = np.random.default_rng(seed)
    parts = [[], [], []]
    for label in sorted(set(labels[indices])):
        members = indices[labels[indices] == label].copy()
        rng.shuffle(members)
        offset = int(rng.integers(3))
        for number, member in enumerate(members):
            parts[(number + offset) % 3].append(member)
    return [np.array(sorted(part), dtype=int) for part in parts]


def predict(candidate, kernels, targets, train, query, loo=False):
    name, method, parameter = candidate
    kernel = kernels[name]
    if method == "knn":
        similarity = kernel[np.ix_(query, train)].copy()
        if loo:
            similarity[query[:, None] == train[None, :]] = -np.inf
        count = min(int(parameter), len(train) - int(loo))
        nearest = np.argsort(-similarity, axis=1, kind="stable")[:, :count]
        values = np.take_along_axis(similarity, nearest, axis=1)
        weights = np.exp((values - values[:, :1]) / 0.05)
        return (targets[train[nearest]] * weights[:, :, None]).sum(axis=1) / weights.sum(axis=1)[:, None]
    system = kernel[np.ix_(train, train)] + float(parameter) * np.eye(len(train))
    inverse = np.linalg.solve(system, np.eye(len(train)))
    coefficients = inverse @ targets[train]
    if loo:
        # Exact leave-one-out predictions for kernel ridge with fixed features.
        return targets[train] - coefficients / np.diag(inverse)[:, None]
    return kernel[np.ix_(query, train)] @ coefficients


def score(prediction, truth):
    return float(np.mean(prediction.argmax(axis=1) == truth))


def name_of(candidate):
    return "{}-{}-{}".format(*candidate)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--out-dir", type=Path, default=Path("output/c1"))
    args = parser.parse_args()
    root = args.root.resolve()
    out = args.out_dir if args.out_dir.is_absolute() else root / args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    slides = json.loads((root / "pack_slides/slides_manifest.json").read_text())["slides"]
    assert len({s["id"] for s in slides}) == len(slides)
    models = ["gigapath", "biomedclip", "hoptimus", "dinov2"]
    vectors = {}
    for model in models:
        records = json.loads((root / f"tilepack/embeddings/{model}/slide-vectors.json").read_text())
        vectors[model] = {record["id"]: record["v"] for record in records}
        assert len(vectors[model]) == len(records), model
    common = set.intersection(*(set(vectors[m]) for m in models))
    labelled = [s for s in slides if not s.get("heldout") and s.get("organGroup") and s["id"] in common]
    excluded = [s["id"] for s in slides if not s.get("heldout") and s.get("organGroup") and s["id"] not in common]
    heldout = [s for s in slides if s.get("heldout")]
    assert all(s["id"] in common for s in heldout), "A held-out slide needs an embedding fallback."
    ordered = labelled + heldout
    classes = sorted({s["organGroup"] for s in labelled})
    truth = np.array([classes.index(s["organGroup"]) for s in labelled])
    targets = np.eye(len(classes))[truth]
    kernels = {}
    for model in models:
        matrix = np.array([vectors[model][s["id"]] for s in ordered], dtype=float)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        assert np.isfinite(matrix).all() and (norms > 0).all(), model
        matrix /= norms
        kernels[model] = matrix @ matrix.T
    # Equivalent to concatenating equally weighted, normalized feature blocks.
    kernels["giga_clip"] = (kernels["gigapath"] + kernels["biomedclip"]) / 2
    candidates = [(m, "knn", k) for m in models + ["giga_clip"] for k in [1, 3, 5]]
    candidates += [(m, "ridge", alpha) for m in ["gigapath", "biomedclip", "giga_clip"] for alpha in [0.01, 0.1, 1.0]]
    indices = np.arange(len(labelled))
    loo_predictions = [predict(c, kernels, targets, indices, indices, loo=True) for c in candidates]
    loo_scores = [score(p, truth) for p in loo_predictions]
    best_index = int(np.argmax(loo_scores))
    selected = candidates[best_index]
    print(f"Labelled: {len(labelled)}; held-out: {len(heldout)}; excluded missing vectors: {excluded}", flush=True)
    for i in sorted(range(len(candidates)), key=lambda i: -loo_scores[i])[:8]:
        print(f"Exploratory LOO: {name_of(candidates[i]):28s} {loo_scores[i]:.3%}", flush=True)

    # Outer validation does not use its labels to select the candidate.
    # Inner selection uses exact leave-one-out within each outer training set.
    nested_rows = []
    outer_scores = []
    baseline_scores = []
    for seed in [17, 29, 43]:
        correct, baseline_correct = 0, 0
        for fold_number, validation in enumerate(folds(indices, truth, seed)):
            train = np.setdiff1d(indices, validation)
            inner_scores = [score(predict(c, kernels, targets, train, train, loo=True), truth[train]) for c in candidates]
            chosen = candidates[int(np.argmax(inner_scores))]
            predictions = predict(chosen, kernels, targets, train, validation).argmax(axis=1)
            baseline = predict(("gigapath", "knn", 1), kernels, targets, train, validation).argmax(axis=1)
            correct += int(np.sum(predictions == truth[validation]))
            baseline_correct += int(np.sum(baseline == truth[validation]))
            for index, prediction in zip(validation, predictions):
                nested_rows.append({"seed": seed, "fold": fold_number, "slide_id": labelled[index]["id"],
                                    "supplier": labelled[index]["supplierId"], "actual": classes[truth[index]],
                                    "prediction": classes[prediction], "method": name_of(chosen)})
        outer_scores.append(correct / len(labelled))
        baseline_scores.append(baseline_correct / len(labelled))
        print(f"Nested CV seed {seed}: selected pipeline {outer_scores[-1]:.3%}; GigaPath 1-NN {baseline_scores[-1]:.3%}", flush=True)

    query = np.arange(len(labelled), len(ordered))
    final_scores = predict(selected, kernels, targets, indices, query)
    final_predictions = final_scores.argmax(axis=1)
    per_model = {m: predict((m, "knn", 1), kernels, targets, indices, query).argmax(axis=1) for m in models}
    submission = [{"slide_id": s["id"], "organ": classes[p]} for s, p in zip(heldout, final_predictions)]
    template = list(csv.DictReader((root / "pack_slides/submission_template_slides_organ.csv").open()))
    expected = [row["slide_id"] for row in template]
    assert len(expected) == len(set(expected)) == len(submission)
    assert set(expected) == {row["slide_id"] for row in submission}
    by_id = {row["slide_id"]: row for row in submission}
    write_csv(out / "submission_organ.csv", ["slide_id", "organ"], [by_id[sid] for sid in expected])
    review = []
    for i, slide in enumerate(heldout):
        ranked = np.argsort(-final_scores[i])
        neighbors = np.argsort(-kernels["gigapath"][query[i], indices])[:3]
        votes = Counter(classes[per_model[m][i]] for m in models)
        review.append({"slide_id": slide["id"], "prediction": classes[ranked[0]], "runner_up": classes[ranked[1]],
                       "score_margin_not_probability": float(final_scores[i, ranked[0]] - final_scores[i, ranked[1]]),
                       "models_agreeing_with_prediction": votes[classes[ranked[0]]],
                       **{m + "_1nn": classes[per_model[m][i]] for m in models},
                       "gigapath_neighbors": json.dumps([{"id": labelled[j]["id"], "organ": labelled[j]["organGroup"],
                                                          "cosine": float(kernels["gigapath"][query[i], j])} for j in neighbors])})
    review.sort(key=lambda r: (r["models_agreeing_with_prediction"], r["score_margin_not_probability"]))
    write_csv(out / "review_queue.csv", list(review[0]), review)
    write_csv(out / "validation_predictions.csv", list(nested_rows[0]), nested_rows)
    by_supplier = defaultdict(list)
    by_class = defaultdict(list)
    for row in nested_rows:
        by_supplier[row["supplier"]].append(row["actual"] == row["prediction"])
        by_class[row["actual"]].append(row["actual"] == row["prediction"])
    summary = {
        "labelled_slides_used": len(labelled), "heldout_slides": len(heldout), "excluded_labelled_ids": excluded,
        "selected_method": name_of(selected), "exploratory_loo_accuracy": loo_scores[best_index],
        "candidates": [{"method": name_of(c), "loo_accuracy": a} for c, a in zip(candidates, loo_scores)],
        "nested_cv": {"design": "3 repeated stratified 3-fold outer splits; inner leave-one-out model selection",
                      "seeds": [17, 29, 43], "accuracy_by_repeat": outer_scores, "mean_accuracy": float(np.mean(outer_scores)),
                      "gigapath_1nn_accuracy_by_repeat": baseline_scores, "gigapath_1nn_mean": float(np.mean(baseline_scores)),
                      "accuracy_by_supplier": {k: sum(v) / len(v) for k, v in by_supplier.items()},
                      "recall_by_organ": {k: sum(v) / len(v) for k, v in by_class.items()}},
        "predicted_counts": dict(Counter(row["organ"] for row in submission)),
        "notes": ["No official held-out answer key was used.",
                  "LOO scores select the final candidate and are exploratory, not independent test accuracy.",
                  "Nested validation estimates candidate selection with less training data than the final model.",
                  "Repeated validation uses the same slides; repeats are not independent samples.",
                  "Slide-level splits cannot rule out patient-level overlap because no patient grouping is supplied.",
                  "Two labelled slides lack GigaPath vectors; all models use the same 188-slide comparison set.",
                  "Review margins and cross-model agreement are not calibrated probabilities."]}
    (out / "validation_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"Selected {name_of(selected)}; wrote {len(submission)} valid rows to {out / 'submission_organ.csv'}")


if __name__ == "__main__":
    main()
