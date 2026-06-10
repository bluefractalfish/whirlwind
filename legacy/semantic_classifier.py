#!/usr/bin/env python3
"""
Drop-in semantic tiling test script for the refactored whirlwind branch.

Run from repo root after installing the branch:
    git checkout refactored
    python -m pip install -e .

Example:
    python scripts/semantic_classifier.py /data/mosaic.tif --out /tmp/semtest --tile-size 512 --stride 512 --device cuda

Output:
    <out>/shards/<semantic_bucket>/*.tar
    <out>/metadata/semantic_manifest.csv
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, Sequence

import numpy as np
from PIL import Image

import torch
import open_clip
from huggingface_hub import hf_hub_download
import rasterio

from whirlwind.domain.plannedwindow import PlannedWindow
from whirlwind.adapters.arrays.scale import scale_to_uint8
from whirlwind.adapters.geo.window_read import RasterioWindowReader
from whirlwind.adapters.io.write_shards import RoutedShardWriter, WriteShardRequest
from whirlwind.bridges.specs.semclass import SCSpec, ArrayLayout
from whirlwind.domain.tile import Tile, TileEncoder, tile_content_stats
from whirlwind.filesystem.files import RasterFile
from whirlwind.prompts.detailed_classes import (
    DETAILED_CLASSES,
    DETAILED_TO_FINAL,
    FINAL_CLASSES,
    PROMPTS_BY_DETAILED_CLASS,
)

def iter_planned_windows(
    raster_path: Path,
    *,
    tile_size: int,
    stride: int,
    drop_partial: bool,
):
    """
    Make tile windows directly.

    This replaces WindowPlanner for the standalone test script.
    """

    with rasterio.open(raster_path) as ds:
        width = ds.width
        height = ds.height

    row_i = 0
    y = 0

    while y < height:
        h = min(tile_size, height - y)

        if drop_partial and h < tile_size:
            break

        col_i = 0
        x = 0

        while x < width:
            w = min(tile_size, width - x)

            if drop_partial and w < tile_size:
                break

            yield PlannedWindow(
                row_i=row_i,
                col_i=col_i,
                x=x,
                y=y,
                w=w,
                h=h,
            )

            col_i += 1
            x += stride

        row_i += 1
        y += stride 

@dataclass(frozen=True)
class SemanticLabel:
    """
    Label object compatible with your current Label protocol.

    Important:
        bucket controls shard routing.

    TileEncoder copies label.bucket into encoded.metadata["bucket"].
    RoutedShardWriter reads encoded.metadata["bucket"] and picks the child ShardWriter.
    """

    bucket: str
    dominant: str
    mixed: bool

    top_class: str
    top_score: float
    second_class: str
    second_score: float

    final_scores: dict[str, float]
    detailed_scores: dict[str, float]

    mostly_threshold: float
    hybrid_second_threshold: float
    bucket_mode: str

    def metadata(self) -> dict[str, Any]:
        return asdict(self)


def resolve_layout(arr: np.ndarray, layout: ArrayLayout) -> Literal["chw", "hwc"]:
    if layout in ("chw", "hwc"):
        return layout

    if arr.ndim != 3:
        raise ValueError("layout='auto' only applies to 3D arrays")

    if arr.shape[0] <= 16 and arr.shape[1] > 16 and arr.shape[2] > 16:
        return "chw"

    if arr.shape[2] <= 16 and arr.shape[0] > 16 and arr.shape[1] > 16:
        return "hwc"

    raise ValueError(f"could not infer tile layout from shape {arr.shape}")


def tile_to_rgb_uint8(
    tile: np.ndarray,
    *,
    layout: ArrayLayout,
    rgb_bands: tuple[int, int, int],
    p_low: float,
    p_high: float,
) -> np.ndarray:
    """Convert raster tile array into RGB uint8 for RemoteCLIP."""

    arr = np.asarray(tile)

    if arr.ndim == 2:
        rgb_float = np.stack([arr, arr, arr], axis=-1)

    elif arr.ndim == 3:
        resolved = resolve_layout(arr, layout)

        if resolved == "chw":
            max_band = arr.shape[0] - 1
            bands = [min(max(b, 0), max_band) for b in rgb_bands]
            rgb_float = np.transpose(arr[bands, :, :], (1, 2, 0))
        else:
            max_band = arr.shape[2] - 1
            bands = [min(max(b, 0), max_band) for b in rgb_bands]
            rgb_float = arr[:, :, bands]
    else:
        raise ValueError(f"expected 2D or 3D tile array, got {arr.shape}")

    return scale_to_uint8(rgb_float, p_low=p_low, p_high=p_high)


class RemoteClipSemanticClassifier:
    """
    Local test classifier.

    The refactored branch already has SCSpec, scale_to_uint8, and the prompt table.
    This file defines the classifier locally so the test script is self-contained.
    """

    def __init__(self, spec: SCSpec) -> None:
        self.spec = spec
        self.device = torch.device(spec.device)

        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            spec.model_name
        )
        self.tokenizer = open_clip.get_tokenizer(spec.model_name)

        checkpoint_path = self._resolve_checkpoint(spec)
        ckpt = torch.load(checkpoint_path, map_location="cpu")

        if isinstance(ckpt, dict) and "state_dict" in ckpt:
            ckpt = ckpt["state_dict"]

        self.model.load_state_dict(ckpt, strict=False)
        self.model = self.model.to(self.device).eval()

        self.detailed_classes = DETAILED_CLASSES
        self.texts: list[str] = []
        self.text_to_class: list[str] = []

        for class_name in self.detailed_classes:
            for prompt in PROMPTS_BY_DETAILED_CLASS[class_name]:
                self.texts.append(prompt)
                self.text_to_class.append(class_name)

        with torch.no_grad():
            text_tokens = self.tokenizer(self.texts).to(self.device)
            text_features = self.model.encode_text(text_tokens)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)

        self.text_features = text_features

        self.prompt_indices_by_class: dict[str, list[int]] = {
            class_name: [
                i for i, mapped in enumerate(self.text_to_class)
                if mapped == class_name
            ]
            for class_name in self.detailed_classes
        }

    def _resolve_checkpoint(self, spec: SCSpec) -> str:
        if spec.checkpoint_path is not None:
            return str(Path(spec.checkpoint_path).expanduser())

        return hf_hub_download(
            repo_id=spec.hf_repo,
            filename=f"RemoteCLIP-{spec.model_name}.pt",
            cache_dir=str(Path(spec.cache_dir).expanduser()),
        )

    def classify_tile(self, tile: np.ndarray) -> SemanticLabel:
        rgb = tile_to_rgb_uint8(
            tile,
            layout=self.spec.layout,
            rgb_bands=self.spec.rgb_bands,
            p_low=self.spec.percentile_low,
            p_high=self.spec.percentile_high,
        )

        image = Image.fromarray(rgb).convert("RGB")
        detailed_scores = self._classify_image(image)
        final_scores = self._collapse_to_final(detailed_scores)

        if self.spec.prefer_structures:
            final_scores = self._prefer_structures_if_close(final_scores)

        return self._label_from_scores(
            final_scores=final_scores,
            detailed_scores=detailed_scores,
        )

    def classify_tiles(self, tiles: Sequence[np.ndarray]) -> list[SemanticLabel]:
        return [self.classify_tile(tile) for tile in tiles]

    def _classify_image(self, image: Image.Image) -> dict[str, float]:
        image_tensor = self.preprocess(image).unsqueeze(0).to(self.device)

        with torch.no_grad():
            image_features = self.model.encode_image(image_tensor)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)

            prompt_logits = (100.0 * image_features @ self.text_features.T).squeeze(0)

            class_logits = []
            for class_name in self.detailed_classes:
                idxs = self.prompt_indices_by_class[class_name]
                class_logits.append(prompt_logits[idxs].mean())

            class_logits_tensor = torch.stack(class_logits)
            class_probs = class_logits_tensor.softmax(dim=0).detach().cpu().numpy()

        return {
            class_name: float(prob)
            for class_name, prob in zip(self.detailed_classes, class_probs)
        }

    def _collapse_to_final(self, detailed_scores: dict[str, float]) -> dict[str, float]:
        scores = {name: 0.0 for name in FINAL_CLASSES}

        for detailed_class, score in detailed_scores.items():
            final_class = DETAILED_TO_FINAL.get(detailed_class, "mixed")
            scores[final_class] += float(score)

        total = sum(scores.values())
        if total > 0:
            scores = {k: float(v / total) for k, v in scores.items()}

        return scores

    def _prefer_structures_if_close(
        self,
        final_scores: dict[str, float],
    ) -> dict[str, float]:
        scores = dict(final_scores)

        top_class = max(scores, key=scores.get)
        top_score = float(scores[top_class])
        structure_score = float(scores.get("structures", 0.0))

        if (
            top_class in {"roads", "tracks", "dirt", "shadow", "mixed"}
            and structure_score >= self.spec.min_structure_score
            and top_score - structure_score <= self.spec.structure_margin
        ):
            scores["structures"] = top_score + 0.001
            scores[top_class] = max(0.0, structure_score - 0.001)

        total = sum(scores.values())
        if total > 0:
            scores = {k: float(v / total) for k, v in scores.items()}

        return scores

    def _label_from_scores(
        self,
        *,
        final_scores: dict[str, float],
        detailed_scores: dict[str, float],
    ) -> SemanticLabel:
        ranked = sorted(final_scores.items(), key=lambda kv: kv[1], reverse=True)

        top_class, top_score = ranked[0]
        second_class, second_score = ranked[1] if len(ranked) > 1 else ("none", 0.0)

        mixed = (
            top_score < self.spec.mostly_threshold
            or second_score >= self.spec.hybrid_second_threshold
        )

        bucket = self._bucket_name(
            top_class=top_class,
            second_class=second_class,
            second_score=float(second_score),
            mixed=mixed,
        )

        dominant = "mixed" if mixed else top_class

        return SemanticLabel(
            bucket=bucket,
            dominant=dominant,
            mixed=mixed,
            top_class=top_class,
            top_score=float(top_score),
            second_class=second_class,
            second_score=float(second_score),
            final_scores=final_scores,
            detailed_scores=detailed_scores,
            mostly_threshold=self.spec.mostly_threshold,
            hybrid_second_threshold=self.spec.hybrid_second_threshold,
            bucket_mode=self.spec.bucket_mode,
        )

    def _bucket_name(
        self,
        *,
        top_class: str,
        second_class: str,
        second_score: float,
        mixed: bool,
    ) -> str:
        if not mixed:
            return f"mostly_{top_class}"

        if self.spec.bucket_mode == "mostly":
            return "mixed"

        if (
            self.spec.bucket_mode == "hybrid"
            and second_score >= self.spec.hybrid_second_threshold
        ):
            return f"hybrid_{top_class}_{second_class}"

        return "mixed"


class SemanticClassifierLabeler:
    """Adapter from classifier to your Labeler shape."""

    def __init__(self, classifier: RemoteClipSemanticClassifier) -> None:
        self.classifier = classifier

    def label(self, tile: Tile) -> SemanticLabel:
        if tile.read is None:
            raise ValueError("cannot classify tile with tile.read is None")
        return self.classifier.classify_tile(tile.read.array)


class ManifestCsvWriter:
    """Standalone manifest writer for this test script."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.f = self.path.open("w", newline="", encoding="utf-8")
        self.writer: csv.DictWriter | None = None

    def write(self, row: Any) -> None:
        record = asdict(row)

        if self.writer is None:
            self.writer = csv.DictWriter(self.f, fieldnames=list(record.keys()))
            self.writer.writeheader()

        self.writer.writerow(record)
        self.f.flush()

    def close(self) -> None:
        self.f.close()


def parse_rgb_bands(value: str) -> tuple[int, int, int]:
    parts = [int(x.strip()) for x in value.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("rgb bands must look like 0,1,2")
    return (parts[0], parts[1], parts[2])


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Tile a raster and write RemoteCLIP semantic bucket shards."
    )

    p.add_argument("--out", type=Path, required=True, help="Output directory.")

    p.add_argument("--tile-size", type=int, default=512)
    p.add_argument("--stride", type=int, default=512)
    p.add_argument("--drop-partial", action="store_true", default=True)
    p.add_argument("--keep-partial", dest="drop_partial", action="store_false")

    p.add_argument("--shard-size", type=int, default=2048)
    p.add_argument("--prefix", type=str, default="semantic_tile")

    p.add_argument("--masked", action="store_true", default=False)
    p.add_argument("--fill-value", type=float, default=0.0)

    p.add_argument("--keep-empty", action="store_true", default=False)
    p.add_argument("--min-content-fraction", type=float, default=0.05)
    p.add_argument("--zero-is-empty", action="store_true", default=True)
    p.add_argument("--zero-is-not-empty", dest="zero_is_empty", action="store_false")

    p.add_argument("--max-tiles", type=int, default=None)

    p.add_argument("--device", type=str, default="cpu")
    p.add_argument("--cache-dir", type=str, default="~/.cache/remoteclip")
    p.add_argument("--checkpoint-path", type=str, default=None)
    p.add_argument("--model-name", type=str, default="ViT-B-32")
    p.add_argument("--hf-repo", type=str, default="chendelong/RemoteCLIP")

    p.add_argument("--layout", choices=["auto", "chw", "hwc"], default="chw")
    p.add_argument("--rgb-bands", type=parse_rgb_bands, default=(0, 1, 2))
    p.add_argument("--percentile-low", type=float, default=2.0)
    p.add_argument("--percentile-high", type=float, default=98.0)

    p.add_argument("--bucket-mode", choices=["mostly", "hybrid"], default="hybrid")
    p.add_argument("--mostly-threshold", type=float, default=0.60)
    p.add_argument("--hybrid-second-threshold", type=float, default=0.25)

    p.add_argument("--no-prefer-structures", action="store_true")
    p.add_argument("--structure-margin", type=float, default=0.08)
    p.add_argument("--min-structure-score", type=float, default=0.22)

    p.add_argument(
        "--write-plan",
        action="store_true",
        help="Write out/metadata/tile_plan.csv and then read from it.",
    )

    p.add_argument("--print-every", type=int, default=25)

    return p


def main() -> int:
    args = build_parser().parse_args()

    raster_path = Path("/home/rhea/C/2023_02_26_Norman_OK/2023_02_26_Norman_OK_S9-14/2023_02_26_Norman_OK_S9-14_RGB_byt.tif").expanduser().resolve()
    out_dir = args.out.expanduser().resolve()

    if not raster_path.exists():
        raise FileNotFoundError(raster_path)

    shards_dir = out_dir / "shards"
    metadata_dir = out_dir / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    print(f"raster: {raster_path}")
    print(f"out:    {out_dir}")


    sc_spec = SCSpec(
        cache_dir=args.cache_dir,
        model_name=args.model_name,
        checkpoint_path=args.checkpoint_path,
        hf_repo=args.hf_repo,
        device=args.device,
        layout=args.layout,
        rgb_bands=args.rgb_bands,
        percentile_low=args.percentile_low,
        percentile_high=args.percentile_high,
        bucket_mode=args.bucket_mode,
        mostly_threshold=args.mostly_threshold,
        hybrid_second_threshold=args.hybrid_second_threshold,
        prefer_structures=not args.no_prefer_structures,
        structure_margin=args.structure_margin,
        min_structure_score=args.min_structure_score,
    )

    print("loading RemoteCLIP classifier...")
    classifier = RemoteClipSemanticClassifier(sc_spec)
    labeler = SemanticClassifierLabeler(classifier)


    plan_path = metadata_dir / "tile_plan.csv"
    rows = iter_planned_windows(
    raster_path,
    tile_size=args.tile_size,
    stride=args.stride,
    drop_partial=args.drop_partial,
    )

    encoder = TileEncoder(src=RasterFile(raster_path))

    shard_request = WriteShardRequest.from_path(
        out_path=shards_dir,
        prefix=args.prefix,
        size=args.shard_size,
    )

    manifest = ManifestCsvWriter(metadata_dir / "semantic_manifest.csv")
    bucket_counts: Counter[str] = Counter()

    n_seen = 0
    n_written = 0
    n_skipped_empty = 0

    try:
        with RoutedShardWriter(shard_request) as writer:
            with RasterioWindowReader(
                raster_path,
                masked=args.masked,
                fill=args.fill_value,
            ) as reader:
                for tile in reader.tiles_from_rows(rows):
                    n_seen += 1

                    if args.max_tiles is not None and n_seen > args.max_tiles:
                        break

                    if not args.keep_empty:
                        stats = tile_content_stats(
                            tile,
                            min_content_fraction=args.min_content_fraction,
                            zero_is_empty=args.zero_is_empty,
                        )
                        if stats.mostly_empty:
                            n_skipped_empty += 1
                            continue

                    label = labeler.label(tile)

                    # TileEncoder writes label.bucket into encoded.metadata["bucket"].
                    encoded = encoder.encode(tile, label)

                    # RoutedShardWriter routes using encoded.metadata["bucket"].
                    placement = writer.write(encoded)

                    row = encoded.as_manifest_row(placement.shard_path)
                    manifest.write(row)

                    bucket_counts[label.bucket] += 1
                    n_written += 1

                    if args.print_every > 0 and n_written % args.print_every == 0:
                        print(
                            f"written={n_written} "
                            f"seen={n_seen} "
                            f"bucket={label.bucket} "
                            f"top={label.top_class}:{label.top_score:.3f} "
                            f"second={label.second_class}:{label.second_score:.3f}"
                        )

    finally:
        manifest.close()

    print("\nsummary")
    print(f"seen:          {n_seen}")
    print(f"written:       {n_written}")
    print(f"skipped_empty: {n_skipped_empty}")
    print(f"manifest:      {metadata_dir / 'semantic_manifest.csv'}")
    print(f"shards:        {shards_dir}")

    print("\nbuckets")
    for bucket, count in bucket_counts.most_common():
        print(f"  {bucket}: {count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
