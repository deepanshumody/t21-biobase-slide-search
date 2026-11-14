#!/usr/bin/env python3
"""Organ-aware C2 retrieval with nested, mixed-gallery internal validation."""
import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from c1_embeddings import write_csv
from c1_features import load_features, make_kernels
from c1_screen import ridge_fit, ridge_loo

FEATURES = ("anchor_dinov2_quantiles", "anchor_hoptimus_quantiles", "giga_clip_0.75")
ALPHAS = (0.003, 0.01, 0.03, 0.1, 0.3, 1.0)
TEMPERATURES = (0.05, 0.075, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0)
WEIGHTS = (0.0, 0.25, 0.5, 0.75, 1.0)
KS = (1, 5, 10)
SEEDS = (1201, 1301, 1409, 1511, 1601)
INNER_OFFSETS = (0, 17, 43)


def split_folds(indices, labels, seed, count=4):
    """Stratify slides, spreading rare groups without requiring four members."""
    rng = np.random.default_rng(seed)
    parts = [[] for _ in range(count)]
    offset = 0
    for label in sorted(set(labels[indices])):
        members = indices[labels[indices] == label].copy()
        rng.shuffle(members)
        for number, member in enumerate(members):
            parts[(offset + number) % count].append(member)
        offset = (offset + len(members)) % count
    return [np.array(sorted(part), dtype=int) for part in parts]


def softmax(scores, temperature):
    shifted = (scores - scores.max(axis=1, keepdims=True)) / temperature
    values = np.exp(shifted)
    return values / values.sum(axis=1, keepdims=True)


def fit_organs(kernels, labels, train):
    """Read labels only at train indices, including regularization/calibration."""
    if not len(train) or np.any(labels[train] < 0):
        raise ValueError("Training requires nonempty, labelled indices")
    n = len(labels)
    # Fixed label vocabulary is supplied by the challenge; no query targets exist.
    classes = kernels["class_count"]
    targets = np.zeros((n, classes))
    targets[train, labels[train]] = 1
    selected, loo_scores, all_scores = [], [], []
    for name in FEATURES:
        candidates = ridge_loo(kernels[name], targets, train, ALPHAS)
        accuracies = [np.mean(p.argmax(axis=1) == labels[train]) for p in candidates]
        best = int(np.argmax(accuracies))
        alpha = ALPHAS[best]
        selected.append({"kernel": name, "alpha": alpha})
        loo_scores.append(candidates[best])
        all_scores.append(ridge_fit(kernels[name], targets, train, np.arange(n), alpha))
    loo = np.mean(loo_scores, axis=0)
    nll = []
    for temperature in TEMPERATURES:
        probabilities = softmax(loo, temperature)
        nll.append(float(-np.log(np.maximum(probabilities[np.arange(len(train)), labels[train]], 1e-15)).mean()))
    temperature = TEMPERATURES[int(np.argmin(nll))]
    probabilities = softmax(np.mean(all_scores, axis=0), temperature)
    # Available gallery labels are certain metadata, not in-sample model outputs.
    probabilities[train] = targets[train]
    return probabilities, {"models": selected, "temperature": temperature,
                           "training_loo_nll": min(nll), "training_slides": len(train)}


def visual_similarity(kernels, present):
    """Missing GigaPath evidence is neutral; do not mix raw model cosine scales."""
    usable = present["gigapath"][:, None] & present["gigapath"][None, :]
    return np.where(usable, kernels["gigapath"], 0.0)


def rank_results(probabilities, similarity, queries, gallery, weight, ids, k=10):
    """Combine expected organ agreement and cosine, with stable visual ties."""
    if not 0 <= weight <= 1:
        raise ValueError("Organ weight must be between zero and one")
    if len(set(gallery.tolist())) != len(gallery):
        raise ValueError("Duplicate gallery indices")
    visual = np.clip((similarity[np.ix_(queries, gallery)] + 1) / 2, 0, 1)
    agreement = probabilities[queries] @ probabilities[gallery].T
    combined = weight * agreement + (1 - weight) * visual
    rows = []
    for position, query in enumerate(queries):
        allowed = gallery != query
        candidates = gallery[allowed]
        if len(candidates) < k:
            raise ValueError("Too few other slides in the gallery")
        order = np.lexsort((ids[candidates], -visual[position, allowed], -combined[position, allowed]))
        rows.append(candidates[order[:k]])
    return np.array(rows, dtype=int)


def precision(labels, queries, ranking):
    if np.any(labels[queries] < 0) or np.any(labels[ranking] < 0):
        raise ValueError("Cannot score slides without reference organ labels")
    relevance = labels[ranking] == labels[queries, None]
    return np.column_stack([relevance[:, :k].mean(axis=1) for k in KS])


def select_weight(kernels, labels, train, similarity, ids, seed):
    """Inner validation uses only the outer training pool as its gallery."""
    records = {weight: [] for weight in WEIGHTS}
    for offset in INNER_OFFSETS:
        for hidden in split_folds(train, labels, seed + offset):
            known = np.setdiff1d(train, hidden)
            probabilities, _ = fit_organs(kernels, labels, known)
            for weight in WEIGHTS:
                ranking = rank_results(probabilities, similarity, hidden, train, weight, ids)
                records[weight].append(precision(labels, hidden, ranking))
    summary = []
    for weight, values in records.items():
        metric = np.concatenate(values).mean(axis=0)
        summary.append({"weight": weight, **{f"p_at_{k}": float(value) for k, value in zip(KS, metric)},
                        "objective": float(metric.mean())})
    # Equal mean of the three announced metrics; ties favor more visual evidence.
    selected = max(summary, key=lambda row: (row["objective"], -row["weight"]))
    return selected["weight"], summary


def validate_submission(rows, expected, valid_ids):
    groups = defaultdict(list)
    for row in rows:
        q, result = row["query_slide_id"], row["result_slide_id"]
        if q not in expected or result not in valid_ids or q == result:
            raise ValueError("Unknown slide, unexpected query, or self-match")
        groups[q].append(row)
    if set(groups) != set(expected) or len(rows) != 10 * len(expected):
        raise ValueError("Submission does not cover every query with ten results")
    for query, matches in groups.items():
        if sorted(int(row["rank"]) for row in matches) != list(range(1, 11)):
            raise ValueError(f"Invalid ranks for {query}")
        if len({row["result_slide_id"] for row in matches}) != 10:
            raise ValueError(f"Duplicate results for {query}")


def metric_dict(values):
    return {f"p_at_{k}": float(value) for k, value in zip(KS, np.mean(values, axis=0))}


def run(root, output, seeds):
    output.mkdir(parents=True, exist_ok=True)
    slides, features, present = load_features(root)
    kernels = make_kernels(features)
    ids = np.array([slide["id"] for slide in slides])
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate manifest IDs")
    classes = sorted({s["organGroup"] for s in slides if s.get("organGroup") and not s.get("heldout")})
    labels = np.array([classes.index(s["organGroup"]) if s.get("organGroup") and not s.get("heldout") else -1 for s in slides])
    kernels["class_count"] = len(classes)
    labelled = np.flatnonzero(labels >= 0)
    evaluation = np.flatnonzero((labels >= 0) & present["gigapath"])
    heldout = np.array([i for i, s in enumerate(slides) if s.get("heldout")])
    gallery = np.arange(len(slides))
    similarity = visual_similarity(kernels, present)
    validation_rows, fold_details = [], []
    print(f"Loaded {len(slides)} slides; {len(labelled)} organ labels; {len(heldout)} queries.", flush=True)
    for seed in seeds:
        repeat = {"baseline": [], "organ": []}
        for fold_number, hidden in enumerate(split_folds(evaluation, labels, seed)):
            known = np.setdiff1d(evaluation, hidden)
            weight, selection = select_weight(kernels, labels, known, similarity, ids, seed + 100 + fold_number)
            probabilities, model = fit_organs(kernels, labels, known)
            baseline = rank_results(probabilities, similarity, hidden, evaluation, 0, ids)
            ranking = rank_results(probabilities, similarity, hidden, evaluation, weight, ids)
            old, new = precision(labels, hidden, baseline), precision(labels, hidden, ranking)
            repeat["baseline"].append(old)
            repeat["organ"].append(new)
            fold_details.append({"seed": seed, "fold": fold_number, "selected_weight": weight,
                                 "inner_selection": selection, "classifier": model,
                                 "hidden_ids": ids[hidden].tolist()})
            for position, query in enumerate(hidden):
                count = int(np.sum(labels[evaluation] == labels[query])) - 1
                row = {"seed": seed, "fold": fold_number, "slide_id": ids[query],
                       "organ": classes[labels[query]], "supplier": slides[query].get("supplierId", ""),
                       "weight": weight, "predicted_organ": classes[probabilities[query].argmax()]}
                for j, k in enumerate(KS):
                    row.update({f"baseline_p_at_{k}": float(old[position, j]),
                                f"new_p_at_{k}": float(new[position, j]),
                                f"ceiling_p_at_{k}": min(count, k) / k})
                row["baseline_results"] = json.dumps(ids[baseline[position]].tolist())
                row["new_results"] = json.dumps(ids[ranking[position]].tolist())
                validation_rows.append(row)
        print(json.dumps({"seed": seed, **{name: metric_dict(np.concatenate(value)) for name, value in repeat.items()}}), flush=True)

    baseline_metrics = np.array([[r[f"baseline_p_at_{k}"] for k in KS] for r in validation_rows])
    new_metrics = np.array([[r[f"new_p_at_{k}"] for k in KS] for r in validation_rows])
    per_slide = defaultdict(list)
    for row, delta in zip(validation_rows, new_metrics - baseline_metrics):
        per_slide[row["slide_id"]].append(delta)
    deltas = np.array([np.mean(value, axis=0) for value in per_slide.values()])
    rng = np.random.default_rng(1709)
    samples = rng.integers(len(deltas), size=(10000, len(deltas)))
    intervals = np.quantile(deltas[samples].mean(axis=1), [0.025, 0.975], axis=0)
    weight, selection = select_weight(kernels, labels, evaluation, similarity, ids, 1801)
    probabilities, model = fit_organs(kernels, labels, labelled)
    ranking = rank_results(probabilities, similarity, heldout, gallery, weight, ids)
    rows, evidence, review = [], [], []
    for position, query in enumerate(heldout):
        organ_order = np.argsort(-probabilities[query], kind="stable")
        matches = ranking[position]
        review.append({"slide_id": ids[query], "predicted_organ": classes[organ_order[0]],
                       "top_organ_score": float(probabilities[query, organ_order[0]]),
                       "runner_up": classes[organ_order[1]],
                       "runner_up_score": float(probabilities[query, organ_order[1]]),
                       "known_label_matches": int(np.sum(labels[matches] >= 0)),
                       "predicted_label_matches": int(np.sum(labels[matches] < 0)),
                       "known_top_organ_available": int(np.sum(labels == organ_order[0]))})
        for rank, result in enumerate(matches, 1):
            row = {"query_slide_id": ids[query], "rank": rank, "result_slide_id": ids[result]}
            rows.append(row)
            evidence.append({**row, "query_predicted_organ": classes[organ_order[0]],
                             "result_organ": classes[labels[result]] if labels[result] >= 0 else classes[probabilities[result].argmax()],
                             "result_organ_source": "provided" if labels[result] >= 0 else "predicted",
                             "organ_agreement_score": float(probabilities[query] @ probabilities[result]),
                             "visual_cosine": float(similarity[query, result]),
                             "visual_model": "gigapath" if present["gigapath"][query] and present["gigapath"][result] else "missing_neutral_zero"})
    template = list(csv.DictReader((root / "pack_slides/submission_template_slides_organ.csv").open()))
    expected = {r["slide_id"] for r in template}
    validate_submission(rows, expected, set(ids))
    # Reproduce the supplied GigaPath baseline with its exact gallery and tie rule.
    baseline_gallery = np.flatnonzero(present["gigapath"])
    if not np.all(present["gigapath"][heldout]):
        raise ValueError("An official query lacks GigaPath; exact baseline cannot cover it")
    baseline_ranking = rank_results(probabilities, kernels["gigapath"], heldout, baseline_gallery, 0, ids)
    baseline_rows = [{"query_slide_id": ids[q], "rank": rank, "result_slide_id": ids[j]}
                     for q, results in zip(heldout, baseline_ranking) for rank, j in enumerate(results, 1)]
    validate_submission(baseline_rows, expected, set(ids))
    fields = ["query_slide_id", "rank", "result_slide_id"]
    write_csv(output / "submission_similar.csv", fields, rows)
    write_csv(output / "baseline_similar.csv", fields, baseline_rows)
    write_csv(output / "retrieval_evidence.csv", list(evidence[0]), evidence)
    review.sort(key=lambda row: (row["top_organ_score"], row["slide_id"]))
    write_csv(output / "review_queue.csv", list(review[0]), review)
    write_csv(output / "validation_predictions.csv", list(validation_rows[0]), validation_rows)
    breakdown = {}
    for field in ["organ", "supplier"]:
        breakdown[field] = {}
        for value in sorted({row[field] for row in validation_rows}):
            subset = [row for row in validation_rows if row[field] == value]
            breakdown[field][value] = {"slides": len(subset) // len(seeds),
                                      **{f"{method}_p_at_{k}": float(np.mean([r[f"{method}_p_at_{k}"] for r in subset]))
                                         for method in ["baseline", "new"] for k in KS}}
    summary = {
        "validation_design": "Five repeated stratified 4-fold outer splits by default; three repeated inner 4-fold runs for retrieval-weight selection; train-only LOO ridge selection and temperature fitting",
        "inner_seed_offsets": list(INNER_OFFSETS),
        "seeds": list(seeds), "labelled_slides": len(labelled), "evaluation_slides": len(evaluation), "heldout_slides": len(heldout),
        "evaluation_gallery": "188 organ-labelled slides with GigaPath vectors; fold labels hidden for classification and gallery scoring; self excluded",
        "runtime": {"numpy": np.__version__},
        "selection_objective": "Unweighted mean of precision at 1, 5 and 10; exact ties favor smaller organ weight",
        "weight_grid": list(WEIGHTS), "temperature_grid": list(TEMPERATURES), "alpha_grid": list(ALPHAS),
        "baseline": metric_dict(baseline_metrics), "organ_aware": metric_dict(new_metrics),
        "paired_gain": metric_dict(new_metrics - baseline_metrics),
        "paired_gain_95pct_slide_bootstrap": {f"p_at_{k}": intervals[:, j].tolist() for j, k in enumerate(KS)},
        "gallery_ceiling": {f"p_at_{k}": float(np.mean([r[f"ceiling_p_at_{k}"] for r in validation_rows])) for k in KS},
        "outer_selected_weights": dict(Counter(str(r["selected_weight"]) for r in fold_details)),
        "final_weight": weight, "final_selection": selection, "final_classifier": model,
        "final_gallery_slides": len(gallery), "final_rows": len(rows), "breakdown": breakdown,
        "limitations": [
            "These are internal estimates, not official challenge scores; no held-out answer key was read.",
            "C1 feature families were previously explored on these labelled slides; new seeds do not create an untouched external test.",
            "Unknown true labels prevent scoring the full 263-slide gallery internally; validation uses the 188-slide labelled subset with a similar labelled/unlabelled mixture.",
            "Both validation methods use the same 188-slide gallery with GigaPath vectors. Final fitting uses all 190 labels; the full 263-slide gallery includes two slides with zero GigaPath evidence.",
            "Ridge softmax scores are temperature-fitted from training LOO estimates, not independently established probability calibration.",
            "Organ agreement is a proxy for retrieval relevance; it does not establish diagnosis, cancer subtype, or patient similarity.",
            "Rare organs cannot fill ten relevant slots in the validation gallery; ceilings are reported.",
            "Slide bootstrap intervals reuse the same folds and do not include model-selection or patient-clustering uncertainty.",
            "Patient IDs were not supplied, so patient-level overlap cannot be excluded.",
        ],
    }
    (output / "validation_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (output / "fold_model_selections.json").write_text(json.dumps(fold_details, indent=2) + "\n")
    tracked = [root / "scripts" / name for name in ["c2_retrieval.py", "c1_features.py", "c1_screen.py", "c1_embeddings.py"]]
    tracked += [root / "pack_slides/slides_manifest.json"]
    for name in ["gigapath", "biomedclip", "hoptimus", "dinov2"]:
        folder = root / "tilepack/embeddings" / name
        tracked.append(folder / "slide-vectors.json")
        if name != "gigapath":
            tracked.extend([folder / "tile-meta.json", folder / "tile-vectors.i8"])
    tracked.extend(sorted(p for p in output.iterdir() if p.suffix in {".csv", ".json"} and p.name != "artifact_hashes.json"))
    hashes = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in tracked}
    (output / "artifact_hashes.json").write_text(json.dumps(hashes, indent=2) + "\n")
    print(json.dumps({key: summary[key] for key in ["baseline", "organ_aware", "paired_gain", "final_weight", "final_rows"]}, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--out-dir", default="output/c2")
    parser.add_argument("--seeds", type=int, nargs="+", default=list(SEEDS))
    args = parser.parse_args()
    root = args.root.resolve()
    run(root, root / args.out_dir, args.seeds)


if __name__ == "__main__":
    main()
