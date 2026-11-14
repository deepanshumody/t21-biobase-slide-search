#!/usr/bin/env python3
"""Nested comparison and reproducible C1 submission using richer image features."""
import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from c1_embeddings import folds, predict, write_csv
from c1_features import load_features, make_kernels
from c1_screen import ridge_fit, ridge_loo

ALPHAS = [0.003, 0.01, 0.03, 0.1, 0.3, 1.]


def select_models(kernels, targets, labels, train, number):
    ranked = []
    for name, kernel in kernels.items():
        for alpha, scores in zip(ALPHAS, ridge_loo(kernel, targets, train, ALPHAS)):
            ranked.append((int(np.sum(scores.argmax(axis=1) == labels[train])), name, alpha))
    # Prespecified deterministic tie-breaking; one representative per feature set.
    ranked.sort(key=lambda r: (-r[0], r[1], r[2]))
    selected = []
    seen = set()
    for correct, name, alpha in ranked:
        if name in seen:
            continue
        selected.append({"kernel": name, "alpha": alpha, "inner_correct": correct, "inner_total": len(train)})
        seen.add(name)
        if len(selected) == number:
            break
    return selected


def ensemble_predict(selected, kernels, targets, train, query):
    return np.mean([ridge_fit(kernels[m["kernel"]], targets, train, query, m["alpha"]) for m in selected], axis=0)


def old_predict(kernels, targets, labels, train, query):
    old = {name: kernels[name] for name in ["gigapath", "biomedclip", "hoptimus", "dinov2"]}
    old["giga_clip"] = kernels["giga_clip_0.5"]
    candidates = [(m, "knn", k) for m in list(old) for k in [1, 3, 5]]
    candidates += [(m, "ridge", a) for m in ["gigapath", "biomedclip", "giga_clip"] for a in [0.01, 0.1, 1.]]
    accuracy = [np.mean(predict(c, old, targets, train, train, loo=True).argmax(axis=1) == labels[train]) for c in candidates]
    return predict(candidates[int(np.argmax(accuracy))], old, targets, train, query)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--include-20x", action="store_true")
    parser.add_argument("--include-overview", action="store_true")
    parser.add_argument("--ensemble-size", type=int, default=3)
    parser.add_argument("--kernels", nargs="+", default=["anchor_dinov2_quantiles", "anchor_hoptimus_quantiles", "giga_clip_0.75"],
                        help="Fixed candidate feature families, with regularization selected inside each training fold")
    parser.add_argument("--all-kernels", action="store_true", help="Use the broad experimental search instead of the stable default")
    parser.add_argument("--seeds", type=int, nargs="+", default=[101, 211, 307, 401, 503, 607, 701, 809, 907, 1009])
    parser.add_argument("--out-dir", default="output/c1_improved")
    args = parser.parse_args()
    root = args.root.resolve()
    out = root / args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    slides, features, present = load_features(root, args.include_20x, args.include_overview)
    kernels = make_kernels(features)
    selection_kernels = kernels if args.all_kernels else {name: kernels[name] for name in args.kernels}
    classes = sorted({s["organGroup"] for s in slides if s.get("organGroup") and not s.get("heldout")})
    labels = np.array([classes.index(s["organGroup"]) if s.get("organGroup") and not s.get("heldout") else -1 for s in slides])
    # Held-out rows have no targets. All fits explicitly index labelled rows only.
    targets = np.zeros((len(slides), len(classes)))
    labelled = np.where(labels >= 0)[0]
    targets[labelled, labels[labelled]] = 1
    common = np.where((labels >= 0) & present["gigapath"])[0]
    heldout = np.array([i for i, s in enumerate(slides) if s.get("heldout")])
    validation_rows, repeat_metrics, choices = [], [], []
    for seed in args.seeds:
        correct_old = correct_new = correct_old_fixed = 0
        for fold_number, validation in enumerate(folds(common, labels, seed)):
            train = np.setdiff1d(common, validation)
            selected = select_models(selection_kernels, targets, labels, train, args.ensemble_size)
            new_scores = ensemble_predict(selected, kernels, targets, train, validation)
            old_scores = old_predict(kernels, targets, labels, train, validation)
            old_fixed_scores = ridge_fit(kernels["giga_clip_0.5"], targets, train, validation, 0.1)
            new_labels, old_labels = new_scores.argmax(axis=1), old_scores.argmax(axis=1)
            old_fixed_labels = old_fixed_scores.argmax(axis=1)
            correct_new += int(np.sum(new_labels == labels[validation]))
            correct_old += int(np.sum(old_labels == labels[validation]))
            correct_old_fixed += int(np.sum(old_fixed_labels == labels[validation]))
            choices.append({"seed": seed, "fold": fold_number, "selected": selected})
            for i, new_label, old_label, old_fixed_label in zip(validation, new_labels, old_labels, old_fixed_labels):
                validation_rows.append({"seed": seed, "fold": fold_number, "slide_id": slides[i]["id"],
                                        "supplier": slides[i]["supplierId"], "organ": classes[labels[i]],
                                        "old_prediction": classes[old_label], "old_fixed_prediction": classes[old_fixed_label],
                                        "new_prediction": classes[new_label]})
        repeat_metrics.append({"seed": seed, "old_accuracy": correct_old / len(common), "new_accuracy": correct_new / len(common),
                               "old_correct": correct_old, "new_correct": correct_new, "slides": len(common),
                               "old_fixed_accuracy": correct_old_fixed / len(common)})
        print(json.dumps(repeat_metrics[-1]), flush=True)
    # Validate the final procedure on all usable labels, including two missing-GigaPath slides.
    all_labelled_metrics = []
    for seed in args.seeds:
        correct = 0
        for validation in folds(labelled, labels, seed):
            train = np.setdiff1d(labelled, validation)
            selected = select_models(selection_kernels, targets, labels, train, args.ensemble_size)
            guesses = ensemble_predict(selected, kernels, targets, train, validation).argmax(axis=1)
            correct += int(np.sum(guesses == labels[validation]))
        all_labelled_metrics.append(correct / len(labelled))
        print(f"190-slide validation seed {seed}: {correct}/{len(labelled)}", flush=True)

    selected = select_models(selection_kernels, targets, labels, labelled, args.ensemble_size)
    final_scores = ensemble_predict(selected, kernels, targets, labelled, heldout)
    all_model_labels = np.array([ridge_fit(kernels[m["kernel"]], targets, labelled, heldout, m["alpha"]).argmax(axis=1) for m in selected])
    final_labels = final_scores.argmax(axis=1)
    previous = {r["slide_id"]: r["organ"] for r in csv.DictReader((root / "output/c1/submission_organ.csv").open())}
    submission = {slides[i]["id"]: classes[y] for i, y in zip(heldout, final_labels)}
    expected = [r["slide_id"] for r in csv.DictReader((root / "pack_slides/submission_template_slides_organ.csv").open())]
    assert len(expected) == len(set(expected)) == len(submission) == 67
    assert set(expected) == set(submission)
    assert set(submission.values()) <= set(classes)
    write_csv(out / "submission_organ.csv", ["slide_id", "organ"], [{"slide_id": sid, "organ": submission[sid]} for sid in expected])
    review = []
    for position, i in enumerate(heldout):
        ranking = np.argsort(-final_scores[position])
        neighbors = common[np.argsort(-kernels["gigapath"][i, common])[:3]]
        review.append({"slide_id": slides[i]["id"], "previous_prediction": previous[slides[i]["id"]],
                       "new_prediction": classes[ranking[0]], "runner_up": classes[ranking[1]],
                       "score_margin_not_probability": float(final_scores[position, ranking[0]] - final_scores[position, ranking[1]]),
                       "ensemble_agreement": int(np.sum(all_model_labels[:, position] == ranking[0])),
                       "ensemble_size": len(selected), "changed": previous[slides[i]["id"]] != classes[ranking[0]],
                       "gigapath_nearest_labelled": json.dumps([{"id": slides[j]["id"], "organ": classes[labels[j]],
                                                                 "cosine": float(kernels["gigapath"][i, j])} for j in neighbors])})
    review.sort(key=lambda r: (r["ensemble_agreement"], r["score_margin_not_probability"]))
    write_csv(out / "review_queue.csv", list(review[0]), review)
    write_csv(out / "submission_changes.csv", ["slide_id", "previous_prediction", "new_prediction"],
              [{key: row[key] for key in ["slide_id", "previous_prediction", "new_prediction"]} for row in review if row["changed"]])
    write_csv(out / "validation_predictions.csv", list(validation_rows[0]), validation_rows)
    per_slide = defaultdict(list)
    by_group = defaultdict(list)
    by_supplier = defaultdict(list)
    for row in validation_rows:
        delta = int(row["new_prediction"] == row["organ"]) - int(row["old_prediction"] == row["organ"])
        per_slide[row["slide_id"]].append(delta)
        by_group[row["organ"]].append((row["old_prediction"] == row["organ"], row["new_prediction"] == row["organ"]))
        by_supplier[row["supplier"]].append((row["old_prediction"] == row["organ"], row["new_prediction"] == row["organ"]))
    # Bootstrap slides rather than treating repeated predictions as independent.
    differences = np.array([np.mean(v) for v in per_slide.values()])
    rng = np.random.default_rng(822)
    bootstrap = rng.choice(differences, size=(10000, len(differences)), replace=True).mean(axis=1)
    summary = {"includes_20x": args.include_20x, "includes_overview": args.include_overview,
               "ensemble_size": args.ensemble_size, "kernel_count": len(selection_kernels),
               "candidate_kernels": list(selection_kernels),
               "alpha_grid": ALPHAS, "selection": "Top distinct kernels by training-only leave-one-out accuracy, averaged equally",
               "paired_common_cohort": len(common), "validation_design": "Repeated stratified 3-fold outer CV with inner leave-one-out model selection",
               "comparison": repeat_metrics, "old_mean_accuracy": float(np.mean([r["old_accuracy"] for r in repeat_metrics])),
               "old_fixed_model_mean_accuracy": float(np.mean([r["old_fixed_accuracy"] for r in repeat_metrics])),
               "new_mean_accuracy": float(np.mean([r["new_accuracy"] for r in repeat_metrics])),
               "paired_gain_95pct_slide_bootstrap": np.quantile(bootstrap, [0.025, 0.975]).tolist(),
               "final_training_slides": len(labelled), "all_labelled_accuracy_by_repeat": all_labelled_metrics,
               "all_labelled_mean_accuracy": float(np.mean(all_labelled_metrics)), "selected_models": selected,
               "changed_predictions": sum(r["changed"] for r in review), "heldout_slides": len(heldout),
               "predicted_counts": dict(Counter(submission.values())),
               "per_organ": {organ: {"old_recall": float(np.mean([v[0] for v in values])), "new_recall": float(np.mean([v[1] for v in values])),
                                      "slides": len(values) // len(args.seeds)} for organ, values in by_group.items()},
               "per_supplier": {supplier: {"old_accuracy": float(np.mean([v[0] for v in values])), "new_accuracy": float(np.mean([v[1] for v in values])),
                                            "slides": len(values) // len(args.seeds)} for supplier, values in by_supplier.items()},
               "notes": ["Official held-out labels were never used.",
                         "Feature families were explored on these labelled data; internal CV is not an untouched external test.",
                         "Selection is nested; every validation slide and its tiles are excluded from all classifier fits for that fold.",
                         "Feature pooling and image encoding use fixed pretrained weights and only the individual slide.",
                         "Missing feature blocks are zero vectors, preserving positive-semidefinite kernels.",
                         "Final fitting uses 190 labelled slides; paired old/new comparison uses exactly the original 188-slide cohort.",
                         "No filename order, supplier identifier, reports, age or sex is used as a predictive feature.",
                         "Repeated folds share slides; bootstrap resamples slides and does not cover every source of uncertainty.",
                         "No patient identifier was supplied, so patient-level overlap cannot be excluded."]}
    (out / "validation_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (out / "fold_model_selections.json").write_text(json.dumps(choices, indent=2) + "\n")
    tracked = [root / "scripts" / name for name in ["c1_embeddings.py", "c1_features.py", "c1_screen.py", "c1_evaluate_improved.py", "c1_extract_20x.py"]]
    tracked += [root / "pack_slides/slides_manifest.json", out / "submission_organ.csv", out / "validation_summary.json"]
    for model in ["gigapath", "biomedclip", "hoptimus", "dinov2"]:
        folder = root / "tilepack/embeddings" / model
        tracked.append(folder / "slide-vectors.json")
        if model != "gigapath":
            tracked.extend([folder / "tile-meta.json", folder / "tile-vectors.i8"])
    hashes = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked}
    (out / "artifact_hashes.json").write_text(json.dumps(hashes, indent=2) + "\n")
    print(json.dumps({k: summary[k] for k in ["old_mean_accuracy", "new_mean_accuracy", "all_labelled_mean_accuracy", "selected_models", "changed_predictions"]}, indent=2))


if __name__ == "__main__":
    main()
