#!/usr/bin/env python3
"""Extract whole-thumbnail and quadrant features with a cached DINOv2 model."""
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps
from torchvision import transforms


def main():
    root = Path(__file__).resolve().parents[1]
    out = root / "output/c1_overview_features"
    out.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(4)
    torch.manual_seed(0)
    checkpoint = Path.home() / ".cache/torch/hub/checkpoints/dinov2_vits14_pretrain.pth"
    model = torch.hub.load(str(Path.home() / ".cache/torch/hub/facebookresearch_dinov2_main"), "dinov2_vits14", source="local", pretrained=False)
    model.load_state_dict(torch.load(checkpoint, map_location="cpu", weights_only=True))
    model.eval()
    transform = transforms.Compose([transforms.ToTensor(), transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225))])
    slides = json.loads((root / "pack_slides/slides_manifest.json").read_text())["slides"]
    metadata = {"model": "dinov2_vits14", "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                "preprocessing": "Crop outer glass by fixed RGB mask; square-pad full view and four quadrants to 224; ImageNet normalization",
                "views": ["full", "top_left", "top_right", "bottom_left", "bottom_right"]}
    (out / "provenance.json").write_text(json.dumps(metadata, indent=2) + "\n")
    start = time.monotonic()
    for number, slide in enumerate(slides, 1):
        path = out / (slide["id"] + ".npz")
        if path.exists():
            continue
        with Image.open(root / "thumbnails" / (slide["id"] + ".jpg")) as image:
            image = image.convert("RGB")
            pixels = np.asarray(image).astype(np.int16)
            tissue = (pixels.max(axis=2) - pixels.min(axis=2) > 15) & (pixels.mean(axis=2) < 240) & (pixels.max(axis=2) > 30)
            ys, xs = np.where(tissue)
            if len(xs) > 100:
                margin = max(2, int(max(image.size) * 0.02))
                image = image.crop((max(0, xs.min() - margin), max(0, ys.min() - margin),
                                    min(image.width, xs.max() + margin + 1), min(image.height, ys.max() + margin + 1)))
            width, height = image.size
            views = [image]
            for top, bottom in [(0, (height + 1) // 2), (height // 2, height)]:
                for left, right in [(0, (width + 1) // 2), (width // 2, width)]:
                    views.append(image.crop((left, top, right, bottom)))
            batch = torch.stack([transform(ImageOps.pad(v, (224, 224), method=Image.Resampling.BICUBIC, color="white")) for v in views])
        with torch.inference_mode():
            result = model.forward_features(batch)
        np.savez_compressed(path, cls=result["x_norm_clstoken"].numpy(), patch=result["x_norm_patchtokens"].mean(dim=1).numpy())
        if number % 40 == 0 or number == len(slides):
            print(f"Overview features: {number}/{len(slides)} slides, {time.monotonic() - start:.1f}s", flush=True)


if __name__ == "__main__":
    main()
