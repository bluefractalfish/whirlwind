from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from skimage.measure import regionprops
from tqdm import tqdm


def normalize_rgb(rgb: np.ndarray) -> np.ndarray:
    """
    Input:  [3, H, W]
    Output: [3, H, W] float32 in 0..1
    """
    rgb = rgb.astype(np.float32)

    max_val = float(np.nanmax(rgb)) if rgb.size else 0.0

    if max_val > 255:
        rgb = rgb / 65535.0
    elif max_val > 1.5:
        rgb = rgb / 255.0

    return np.clip(rgb, 0.0, 1.0)


def excess_green(rgb: np.ndarray) -> np.ndarray:
    """
    RGB-only vegetation proxy.

    ExG = 2G - R - B
    """
    r, g, b = rgb[0], rgb[1], rgb[2]
    return 2.0 * g - r - b


def brightness(rgb: np.ndarray) -> np.ndarray:
    return rgb.mean(axis=0)


def gradient_strength(rgb: np.ndarray) -> np.ndarray:
    gray = rgb.mean(axis=0)
    gy, gx = np.gradient(gray)
    return np.sqrt(gx * gx + gy * gy)


def scale01(x: np.ndarray | float, lo: float, hi: float):
    return np.clip((x - lo) / max(hi - lo, 1e-6), 0.0, 1.0)


def write_float_mask_like(src_path: Path, out_path: Path, arr: np.ndarray) -> None:
    with rasterio.open(src_path) as src:
        profile = src.profile.copy()
        profile.update(
            count=1,
            dtype="float32",
            nodata=0,
            compress="deflate",
            tiled=True,
            blockxsize=256,
            blockysize=256,
        )

        with rasterio.open(out_path, "w", **profile) as dst:
            dst.write(arr.astype(np.float32), 1)


def run_sam(
    image_path: Path,
    sam_objects_path: Path,
    model_type: str = "vit_b",
    device: str | None = None,
) -> None:
    """
    Runs SAM automatic mask generation on the whole downsampled raster.

    Output:
      sam_objects.tif

    Pixel values:
      0 = background
      1, 2, 3, ... = unique SAM object IDs
    """
    from samgeo import SamGeo

    sam_kwargs = {
        "points_per_side": 32,
        "pred_iou_thresh": 0.86,
        "stability_score_thresh": 0.92,
        "crop_n_layers": 1,
        "crop_n_points_downscale_factor": 2,
        "min_mask_region_area": 64,
    }

    sam = SamGeo(
        model_type=model_type,
        automatic=True,
        device=device,
        sam_kwargs=sam_kwargs,
    )

    sam.generate(
        str(image_path),
        output=str(sam_objects_path),
        foreground=True,
        unique=True,
    )


def compute_probability_masks(
    image_path: Path,
    sam_objects_path: Path,
    out_dir: Path,
    rgb_bands: tuple[int, int, int] = (1, 2, 3),
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    with rasterio.open(image_path) as src:
        rgb = src.read(list(rgb_bands))

    rgb = normalize_rgb(rgb)

    with rasterio.open(sam_objects_path) as src:
        labels = src.read(1).astype(np.int32)

    h, w = labels.shape
    total_pixels = h * w

    exg = excess_green(rgb)
    bright = brightness(rgb)
    grad = gradient_strength(rgb)

    # Pixel-level RGB heuristic masks.
    vegetation_prob = scale01(exg, lo=0.02, hi=0.18)

    bare_soil_prob = (
        (1.0 - vegetation_prob)
        * scale01(bright, lo=0.22, hi=0.65)
        * scale01(rgb[0] - rgb[2], lo=-0.05, hi=0.20)
    )

    road_prob = np.zeros((h, w), dtype=np.float32)
    building_prob = np.zeros((h, w), dtype=np.float32)
    field_prob = np.zeros((h, w), dtype=np.float32)

    props = regionprops(labels)

    for prop in tqdm(props, desc="Scoring SAM segments"):
        label_id = prop.label

        if label_id == 0:
            continue

        area = float(prop.area)

        if area < 64:
            continue

        minr, minc, maxr, maxc = prop.bbox
        bbox_h = maxr - minr
        bbox_w = maxc - minc
        bbox_area = max(float(bbox_h * bbox_w), 1.0)

        aspect = max(bbox_h, bbox_w) / max(min(bbox_h, bbox_w), 1)
        rectangularity = area / bbox_area
        area_fraction = area / total_pixels

        mask = labels == label_id

        mean_exg = float(exg[mask].mean())
        mean_brightness = float(bright[mask].mean())
        mean_grad = float(grad[mask].mean())
        mean_veg = float(vegetation_prob[mask].mean())
        mean_soil = float(bare_soil_prob[mask].mean())

        # Long, narrow, low-vegetation objects.
        road_like = (
            scale01(aspect, lo=3.0, hi=12.0)
            * scale01(0.08 - mean_exg, lo=0.0, hi=0.16)
            * scale01(mean_brightness, lo=0.18, hi=0.65)
        )

        # Compact, rectangular, low-vegetation objects.
        compactness = 1.0 - scale01(aspect, lo=1.5, hi=4.0)

        building_like = (
            scale01(rectangularity, lo=0.35, hi=0.85)
            * compactness
            * scale01(0.08 - mean_exg, lo=0.0, hi=0.16)
            * scale01(mean_brightness, lo=0.20, hi=0.75)
        )

        # Large, smoother vegetation regions.
        low_texture = 1.0 - scale01(mean_grad, lo=0.03, hi=0.16)

        field_like = (
            scale01(area_fraction, lo=0.002, hi=0.08)
            * scale01(mean_veg, lo=0.25, hi=0.80)
            * low_texture
        )

        # Suppress roads/buildings inside very green segments.
        if mean_veg > 0.45:
            road_like *= 0.25
            building_like *= 0.25

        # Soil-heavy segments get a small road/track bump if elongated.
        if mean_soil > 0.35 and aspect > 4:
            road_like = max(float(road_like), 0.45)

        road_prob[mask] = max(float(road_prob[mask].max()), float(road_like))
        building_prob[mask] = max(float(building_prob[mask].max()), float(building_like))
        field_prob[mask] = max(float(field_prob[mask].max()), float(field_like))

    # Candidate damage is derived from the other masks.
    damage_candidate_prob = np.clip(
        0.45 * bare_soil_prob
        + 0.30 * road_prob
        + 0.15 * building_prob
        + 0.10 * (1.0 - vegetation_prob),
        0.0,
        1.0,
    )

    write_float_mask_like(image_path, out_dir / "vegetation_prob.tif", vegetation_prob)
    write_float_mask_like(image_path, out_dir / "bare_soil_prob.tif", bare_soil_prob)
    write_float_mask_like(image_path, out_dir / "road_prob.tif", road_prob)
    write_float_mask_like(image_path, out_dir / "building_prob.tif", building_prob)
    write_float_mask_like(image_path, out_dir / "field_prob.tif", field_prob)
    write_float_mask_like(image_path, out_dir / "damage_candidate_prob.tif", damage_candidate_prob)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path, help="Downsampled RGB GeoTIFF")
    parser.add_argument("--out-dir", type=Path, default=Path("sam_test_masks"))
    parser.add_argument("--model-type", default="vit_b", choices=["vit_b", "vit_l", "vit_h"])
    parser.add_argument("--device", default=None, help="cuda or cpu. Default lets SamGeo choose.")
    parser.add_argument("--skip-sam", action="store_true", help="Reuse existing sam_objects.tif")

    args = parser.parse_args()

    image_path = args.image
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    sam_objects_path = out_dir / "sam_objects.tif"

    if not args.skip_sam:
        run_sam(
            image_path=image_path,
            sam_objects_path=sam_objects_path,
            model_type=args.model_type,
            device=args.device,
        )

    compute_probability_masks(
        image_path=image_path,
        sam_objects_path=sam_objects_path,
        out_dir=out_dir,
    )

    print(f"Wrote masks to: {out_dir}")


if __name__ == "__main__":
    main()
