"""Slide-local feature construction shared by C1 experiments and final fitting."""
import json
from pathlib import Path

import numpy as np


def normalize(matrix):
    matrix = np.asarray(matrix, dtype=float)
    return matrix / np.maximum(np.linalg.norm(matrix, axis=-1, keepdims=True), 1e-12)


def load_features(root, include_20x=False, include_overview=False):
    root = Path(root)
    slides = json.loads((root / "pack_slides/slides_manifest.json").read_text())["slides"]
    features = {}
    present = {}
    for model in ["gigapath", "biomedclip", "hoptimus", "dinov2"]:
        folder = root / "tilepack/embeddings" / model
        vectors = {r["id"]: r["v"] for r in json.loads((folder / "slide-vectors.json").read_text())}
        dimension = len(next(iter(vectors.values())))
        features[model] = normalize([vectors.get(s["id"], [0.] * dimension) for s in slides])
        present[model] = np.array([s["id"] in vectors for s in slides])
        if model == "gigapath":
            continue
        meta = json.loads((folder / "tile-meta.json").read_text())
        tile_vectors = np.memmap(folder / "tile-vectors.i8", dtype=np.int8, mode="r", shape=(meta["tiles"], meta["dim"]))
        pooled = {name: [] for name in ["mean", "std", "quantiles"]}
        for slide in slides:
            info = meta["slides"][slide["id"]]
            x = normalize(tile_vectors[info["offset"]:info["offset"] + info["count"]].astype(float) / meta["scale"])
            pooled["mean"].append(x.mean(axis=0))
            pooled["std"].append(x.std(axis=0))
            pooled["quantiles"].append(np.concatenate(np.quantile(x, [0.1, 0.5, 0.9], axis=0)))
        for name, matrix in pooled.items():
            features[model + "_" + name] = normalize(matrix)
    if include_20x:
        pooled = {f"20x_{kind}_{stat}": [] for kind in ["cls", "patch"] for stat in ["mean", "std", "quantiles"]}
        for slide in slides:
            with np.load(root / "output/c1_20x_features" / (slide["id"] + ".npz"), allow_pickle=False) as data:
                for kind in ["cls", "patch"]:
                    x = normalize(data[kind])
                    if len(x):
                        values = {"mean": x.mean(axis=0), "std": x.std(axis=0),
                                  "quantiles": np.concatenate(np.quantile(x, [0.1, 0.5, 0.9], axis=0))}
                    else:
                        values = {"mean": np.zeros(384), "std": np.zeros(384), "quantiles": np.zeros(384 * 3)}
                    for stat, vector in values.items():
                        pooled[f"20x_{kind}_{stat}"].append(vector)
        features.update({name: normalize(matrix) for name, matrix in pooled.items()})
    if include_overview:
        pooled = {f"overview_{kind}_{stat}": [] for kind in ["cls", "patch"] for stat in ["full", "quadrants", "std"]}
        for slide in slides:
            with np.load(root / "output/c1_overview_features" / (slide["id"] + ".npz"), allow_pickle=False) as data:
                for kind in ["cls", "patch"]:
                    x = normalize(data[kind])
                    assert x.shape == (5, 384)
                    for stat, vector in {"full": x[0], "quadrants": x[1:].mean(axis=0), "std": x[1:].std(axis=0)}.items():
                        pooled[f"overview_{kind}_{stat}"].append(vector)
        features.update({name: normalize(matrix) for name, matrix in pooled.items()})
    assert all(np.isfinite(x).all() for x in features.values())
    return slides, features, present


def make_kernels(features):
    base = {name: x @ x.T for name, x in features.items()}
    kernels = {name: base[name] for name in ["gigapath", "biomedclip", "hoptimus", "dinov2"]}
    for weight in [0.25, 0.5, 0.75]:
        kernels[f"giga_clip_{weight}"] = weight * base["gigapath"] + (1 - weight) * base["biomedclip"]
    kernels["giga_hoptimus"] = 0.75 * base["gigapath"] + 0.25 * base["hoptimus"]
    kernels["giga_clip_hoptimus"] = 0.5 * base["gigapath"] + 0.25 * base["biomedclip"] + 0.25 * base["hoptimus"]
    anchor = kernels["giga_clip_0.5"]
    for model in ["biomedclip", "hoptimus", "dinov2"]:
        for stat in ["std", "quantiles"]:
            kernels[f"anchor_{model}_{stat}"] = 0.75 * anchor + 0.25 * base[f"{model}_{stat}"]
    # Fixed bandwidths and weights use no label- or dataset-fitted transforms.
    for model in ["gigapath", "giga_clip_0.5", "giga_clip_hoptimus"]:
        linear = kernels[model]
        distance = np.maximum(np.diag(linear)[:, None] + np.diag(linear)[None, :] - 2 * linear, 0)
        for gamma in [1., 3., 10.]:
            kernels[f"{model}_rbf_{gamma}"] = np.exp(-gamma * distance)
    if "20x_cls_mean" in base:
        kernels["20x_cls_mean"] = base["20x_cls_mean"]
        kernels["20x_patch_mean"] = base["20x_patch_mean"]
        for kind in ["cls", "patch"]:
            for weight in [0.25, 0.5]:
                kernels[f"anchor_20x_{kind}_{weight}"] = (1 - weight) * anchor + weight * base[f"20x_{kind}_mean"]
            kernels[f"anchor_20x_{kind}_stats"] = 0.5 * anchor + 0.25 * base[f"20x_{kind}_mean"] + 0.25 * base[f"20x_{kind}_std"]
    if "overview_cls_full" in base:
        for kind in ["cls", "patch"]:
            for stat in ["full", "quadrants"]:
                name = f"overview_{kind}_{stat}"
                kernels[name] = base[name]
                kernels["anchor_" + name] = 0.75 * anchor + 0.25 * base[name]
    return kernels
