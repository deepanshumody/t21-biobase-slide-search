#!/usr/bin/env python3
"""Extract cached DINOv2 features from nonblank 20x tiles, without network access."""
import argparse
import csv
import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torchvision import transforms


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--model-repo", type=Path, default=Path.home() / ".cache/torch/hub/facebookresearch_dinov2_main")
    parser.add_argument("--checkpoint", type=Path, default=Path.home() / ".cache/torch/hub/checkpoints/dinov2_vits14_pretrain.pth")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()
    torch.set_num_threads(args.threads)
    torch.manual_seed(0)
    root = args.root.resolve()
    out = root / "output/c1_20x_features"
    out.mkdir(parents=True, exist_ok=True)
    checkpoint_hash = hashlib.sha256(args.checkpoint.read_bytes()).hexdigest()
    preprocessing = {"resize": 256, "crop": 224, "interpolation": "bicubic", "normalization": "ImageNet"}
    provenance = {"model": "dinov2_vits14", "checkpoint_sha256": checkpoint_hash, "preprocessing": preprocessing,
                  "torch_version": torch.__version__, "device": "cpu", "blank_list_sha256": hashlib.sha256((root / "tiles20x/blank_tiles.csv").read_bytes()).hexdigest()}
    config_file = out / "provenance.json"
    if config_file.exists():
        assert json.loads(config_file.read_text()) == provenance, "Feature cache configuration changed."
    config_file.write_text(json.dumps(provenance, indent=2) + "\n")
    model = torch.hub.load(str(args.model_repo), "dinov2_vits14", source="local", pretrained=False)
    model.load_state_dict(torch.load(args.checkpoint, map_location="cpu", weights_only=True), strict=True)
    model.eval()
    transform = transforms.Compose([
        transforms.Resize(256, interpolation=transforms.InterpolationMode.BICUBIC),
        transforms.CenterCrop(224), transforms.ToTensor(),
        transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
    ])
    with (root / "tiles20x/blank_tiles.csv").open() as stream:
        blank = {r["file"] for r in csv.DictReader(stream)}
    by_slide = defaultdict(list)
    with (root / "tiles20x/tiles20x.csv").open() as stream:
        all_tiles = list(csv.DictReader(stream))
    for row in all_tiles:
        by_slide[row["slide_id"]]
        if row["file"] not in blank:
            by_slide[row["slide_id"]].append(row["file"])
    started = time.monotonic()
    processed = 0
    for number, (slide_id, files) in enumerate(sorted(by_slide.items()), 1):
        path = out / f"{slide_id}.npz"
        if path.exists():
            with np.load(path, allow_pickle=False) as data:
                assert data["files"].tolist() == files
                assert data["cls"].shape == (len(files), 384)
            processed += len(files)
            continue
        cls_features, patch_features = [], []
        with torch.inference_mode():
            for start in range(0, len(files), args.batch_size):
                images = []
                for filename in files[start:start + args.batch_size]:
                    with Image.open(root / "tiles20x" / filename) as image:
                        images.append(transform(image.convert("RGB")))
                result = model.forward_features(torch.stack(images))
                cls_features.append(result["x_norm_clstoken"].cpu().numpy())
                patch_features.append(result["x_norm_patchtokens"].mean(dim=1).cpu().numpy())
        cls = np.concatenate(cls_features) if files else np.empty((0, 384), dtype=np.float32)
        patch = np.concatenate(patch_features) if files else np.empty((0, 384), dtype=np.float32)
        assert np.isfinite(cls).all() and np.isfinite(patch).all()
        temporary = path.with_suffix(".tmp.npz")
        np.savez_compressed(temporary, files=np.array(files, dtype=str), cls=cls, patch=patch)
        temporary.replace(path)
        processed += len(files)
        if number % 10 == 0 or number == len(by_slide):
            print(f"{number}/{len(by_slide)} slides; {processed} usable tiles; {time.monotonic() - started:.1f}s", flush=True)
    summary = {"slides": len(by_slide), "tiles_total": len(all_tiles), "tiles_excluded": len(blank),
               "tiles_embedded": processed, "slides_without_usable_tiles": [s for s, files in by_slide.items() if not files]}
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
