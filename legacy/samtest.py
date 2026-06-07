from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Literal
from io import BytesIO
import argparse
import json
import tarfile

import numpy as np
from PIL import Image
import torch


ArrayLayout = Literal["auto", "chw", "hwc"]
MaskMode = Literal["instance", "binary"]
CropMode = Literal["context", "masked"]


# ---------------------------------------------------------------------
# SAMGEO TILE MASKING
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class SamGeoTileMaskSpec:
    model_type: str = "vit_b"
    checkpoint: str | None = None
    device: str = "cpu"

    layout: ArrayLayout = "chw"
    rgb_bands: tuple[int, int, int] = (0, 1, 2)

    mask_mode: MaskMode = "instance"
    foreground: bool = True
    unique: bool = True

    points_per_side: int = 32
    pred_iou_thresh: float = 0.86
    stability_score_thresh: float = 0.92
    min_mask_region_area: int = 64

    percentile_low: float = 2.0
    percentile_high: float = 98.0


@dataclass
class SamGeoTileMaskResult:
    mask: np.ndarray
    metadata: dict[str, Any]


class SamGeoTileMasker:
    def __init__(self, spec: SamGeoTileMaskSpec) -> None:
        self.spec = spec
        self._sam = self._build_samgeo()

    def run(self, tile: np.ndarray, tile_id: str | None = None) -> SamGeoTileMaskResult:
        rgb = tile_to_rgb_uint8(
            tile,
            layout=self.spec.layout,
            rgb_bands=self.spec.rgb_bands,
            p_low=self.spec.percentile_low,
            p_high=self.spec.percentile_high,
        )

        raw_mask = self._generate_mask(rgb)
        mask = normalize_mask(raw_mask, mode=self.spec.mask_mode)

        metadata = summarize_mask(
            mask=mask,
            tile_id=tile_id,
            spec=self.spec,
            input_shape=tuple(tile.shape),
            rgb_shape=tuple(rgb.shape),
        )

        return SamGeoTileMaskResult(mask=mask, metadata=metadata)

    def _build_samgeo(self) -> Any:
        try:
            from samgeo import SamGeo
        except ImportError as exc:
            raise ImportError(
                "samgeo is not installed. Try: pip install segment-geospatial"
            ) from exc

        sam_kwargs = {
            "points_per_side": self.spec.points_per_side,
            "pred_iou_thresh": self.spec.pred_iou_thresh,
            "stability_score_thresh": self.spec.stability_score_thresh,
            "min_mask_region_area": self.spec.min_mask_region_area,
        }

        kwargs: dict[str, Any] = {
            "model_type": self.spec.model_type,
            "sam_kwargs": sam_kwargs,
        }

        if self.spec.checkpoint is not None:
            kwargs["checkpoint"] = self.spec.checkpoint

        try:
            return SamGeo(device=self.spec.device, **kwargs)
        except TypeError:
            return SamGeo(**kwargs)

    def _generate_mask(self, rgb: np.ndarray) -> np.ndarray:
        with TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            image_path = tmp_dir / "tile.png"
            mask_path = tmp_dir / "sam_mask.tif"

            Image.fromarray(rgb).save(image_path)

            try:
                self._sam.generate(
                    str(image_path),
                    str(mask_path),
                    foreground=self.spec.foreground,
                    unique=self.spec.unique,
                )
            except TypeError:
                self._sam.generate(str(image_path), str(mask_path))

            return read_mask_image(mask_path)


# ---------------------------------------------------------------------
# ARRAY CONVERSION
# ---------------------------------------------------------------------


def tile_to_rgb_uint8(
    tile: np.ndarray,
    layout: ArrayLayout = "auto",
    rgb_bands: tuple[int, int, int] = (0, 1, 2),
    p_low: float = 2.0,
    p_high: float = 98.0,
) -> np.ndarray:
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
        raise ValueError(f"Expected 2D or 3D tile array, got shape {arr.shape}")

    return scale_to_uint8(rgb_float, p_low=p_low, p_high=p_high)


def resolve_layout(arr: np.ndarray, layout: ArrayLayout) -> Literal["chw", "hwc"]:
    if layout in ("chw", "hwc"):
        return layout

    if arr.ndim != 3:
        raise ValueError("layout='auto' only applies to 3D arrays")

    if arr.shape[0] <= 16 and arr.shape[1] > 16 and arr.shape[2] > 16:
        return "chw"

    if arr.shape[2] <= 16 and arr.shape[0] > 16 and arr.shape[1] > 16:
        return "hwc"

    raise ValueError(
        f"Could not infer tile layout from shape {arr.shape}. "
        "Pass layout='chw' or layout='hwc'."
    )


def scale_to_uint8(
    arr: np.ndarray,
    p_low: float = 2.0,
    p_high: float = 98.0,
) -> np.ndarray:
    x = np.asarray(arr)

    if x.dtype == np.uint8:
        return x.copy()

    x = x.astype(np.float32)
    out = np.zeros(x.shape, dtype=np.uint8)

    for c in range(x.shape[-1]):
        band = x[..., c]
        finite = np.isfinite(band)

        if not finite.any():
            continue

        vals = band[finite]
        raw_min = float(vals.min())
        raw_max = float(vals.max())

        if raw_max <= raw_min:
            out[..., c].fill(255 if raw_max > 0 else 0)
            continue

        lo = float(np.percentile(vals, p_low))
        hi = float(np.percentile(vals, p_high))

        if hi <= lo:
            lo = raw_min
            hi = raw_max

        y = (band - lo) / (hi - lo)
        y = np.clip(y, 0.0, 1.0)
        y[~finite] = 0.0

        out[..., c] = (y * 255.0).round().astype(np.uint8)

    return out


def read_mask_image(path: str | Path) -> np.ndarray:
    path = Path(path)

    try:
        import rasterio

        with rasterio.open(path) as src:
            return src.read(1)
    except Exception:
        img = Image.open(path)
        return np.asarray(img)


def normalize_mask(mask: np.ndarray, mode: MaskMode) -> np.ndarray:
    arr = np.asarray(mask)

    if arr.ndim == 3:
        arr = arr[..., 0]

    if mode == "binary":
        return (arr > 0).astype(np.uint8)

    if arr.max(initial=0) <= np.iinfo(np.uint16).max:
        return arr.astype(np.uint16)

    return arr.astype(np.uint32)


def summarize_mask(
    mask: np.ndarray,
    tile_id: str | None,
    spec: SamGeoTileMaskSpec,
    input_shape: tuple[int, ...],
    rgb_shape: tuple[int, ...],
) -> dict[str, Any]:
    foreground = mask > 0
    area = int(mask.size)
    fg_pixels = int(foreground.sum())

    ids = np.unique(mask)
    object_ids = ids[ids != 0]

    object_areas: list[int] = []
    if object_ids.size:
        counts = np.bincount(mask.astype(np.int64).ravel())
        object_areas = [
            int(counts[int(i)])
            for i in object_ids
            if int(i) < len(counts)
        ]

    largest_object_area = max(object_areas) if object_areas else 0

    return {
        "tile_id": tile_id,
        "operator": "SamGeoTileMasker",
        "input_shape": input_shape,
        "rgb_shape": rgb_shape,
        "mask_shape": tuple(mask.shape),
        "mask_dtype": str(mask.dtype),
        "mask_mode": spec.mask_mode,
        "samgeo": {
            "model_type": spec.model_type,
            "checkpoint": spec.checkpoint,
            "device": spec.device,
            "points_per_side": spec.points_per_side,
            "pred_iou_thresh": spec.pred_iou_thresh,
            "stability_score_thresh": spec.stability_score_thresh,
            "min_mask_region_area": spec.min_mask_region_area,
        },
        "object_mask": {
            "num_objects": int(object_ids.size),
            "foreground_pixels": fg_pixels,
            "foreground_fraction": float(fg_pixels / area) if area else 0.0,
            "largest_object_pixels": int(largest_object_area),
            "largest_object_fraction": float(largest_object_area / area) if area else 0.0,
        },
    }


# ---------------------------------------------------------------------
# DETAILED REMOTECLIP CLASS TAXONOMY
# ---------------------------------------------------------------------


DETAILED_CLASSES: tuple[str, ...] = (
    # Trees / woody vegetation
    "deciduous_tree_canopy",
    "conifer_tree_canopy",
    "individual_tree_crown",
    "dense_tree_stand",
    "shrub_or_brush",

    # Grass / low vegetation
    "mowed_lawn_grass",
    "pasture_grass",
    "rough_rangeland_grass",
    "green_field_low_vegetation",

    # Structures
    "single_family_house_roof",
    "rectangular_building_roof",
    "dark_shingle_roof",
    "light_roof_or_concrete_roof",
    "metal_roof_building",
    "small_shed_or_outbuilding",
    "farm_or_industrial_structure",
    "damaged_or_broken_structure",

    # Roads / paved surfaces
    "asphalt_road",
    "concrete_road",
    "gravel_road",
    "driveway_or_parking_area",
    "linear_track_or_tire_path",

    # Dirt / soil / agriculture
    "bare_soil",
    "tilled_dirt",
    "dry_bare_ground",
    "crop_rows_on_bare_soil",
    "green_crop_field",

    # Other explicit classes
    "water",
    "deep_shadow",
    "vehicle",
    "debris_or_rubble",
    "unknown_mixed_landcover",
)

FINAL_CLASSES: tuple[str, ...] = (
    "trees",
    "grass",
    "structures",
    "roads",
    "dirt",
    "crops",
    "water",
    "shadow",
    "vehicles",
    "debris",
    "other",
)

DETAILED_TO_FINAL: dict[str, str] = {
    "deciduous_tree_canopy": "trees",
    "conifer_tree_canopy": "trees",
    "individual_tree_crown": "trees",
    "dense_tree_stand": "trees",
    "shrub_or_brush": "trees",

    "mowed_lawn_grass": "grass",
    "pasture_grass": "grass",
    "rough_rangeland_grass": "grass",
    "green_field_low_vegetation": "grass",

    "single_family_house_roof": "structures",
    "rectangular_building_roof": "structures",
    "dark_shingle_roof": "structures",
    "light_roof_or_concrete_roof": "structures",
    "metal_roof_building": "structures",
    "small_shed_or_outbuilding": "structures",
    "farm_or_industrial_structure": "structures",
    "damaged_or_broken_structure": "structures",

    "asphalt_road": "roads",
    "concrete_road": "roads",
    "gravel_road": "roads",
    "driveway_or_parking_area": "roads",
    "linear_track_or_tire_path": "roads",

    "bare_soil": "dirt",
    "tilled_dirt": "dirt",
    "dry_bare_ground": "dirt",
    "crop_rows_on_bare_soil": "crops",
    "green_crop_field": "crops",

    "water": "water",
    "deep_shadow": "shadow",
    "vehicle": "vehicles",
    "debris_or_rubble": "debris",
    "unknown_mixed_landcover": "other",
}

PROMPTS_BY_DETAILED_CLASS: dict[str, list[str]] = {
    "deciduous_tree_canopy": [
        "a submeter overhead aerial image of broadleaf deciduous tree canopy with rounded green crowns",
        "a nadir remote sensing crop showing leafy deciduous tree crowns and irregular organic edges",
        "an orthomosaic patch of mature deciduous trees with textured green canopy",
        "an aerial view of broad green tree crowns casting small shadows",
    ],
    "conifer_tree_canopy": [
        "a submeter overhead aerial image of conifer evergreen trees with dark green pointed crowns",
        "a nadir remote sensing crop showing pine or cedar tree canopy",
        "an orthomosaic patch of dark evergreen trees with compact crown texture",
        "an aerial view of conifer tree crowns, darker than grass and more textured",
    ],
    "individual_tree_crown": [
        "a single isolated tree crown in an overhead aerial image",
        "one round tree canopy object separated from nearby ground in a remote sensing crop",
        "a nadir aerial crop centered on an individual tree crown",
        "a single green woody vegetation crown with shadow in an orthomosaic",
    ],
    "dense_tree_stand": [
        "a dense continuous stand of trees in overhead aerial imagery",
        "a remote sensing crop filled mostly by connected tree canopy",
        "an orthomosaic patch of forest canopy with overlapping crowns",
        "a high resolution aerial image of dense woody vegetation",
    ],
    "shrub_or_brush": [
        "an overhead aerial image of low shrubs or brush with irregular green woody texture",
        "a remote sensing crop of scrub vegetation, not smooth lawn grass",
        "an orthomosaic patch of bushy vegetation with uneven clumps",
        "a nadir image of scattered shrubs and brushy vegetation",
    ],

    "mowed_lawn_grass": [
        "a submeter overhead aerial image of smooth mowed lawn grass",
        "a nadir remote sensing crop showing uniform short green grass near buildings",
        "an orthomosaic patch of smooth bright lawn with little texture",
        "an aerial image of maintained turf grass with even color",
    ],
    "pasture_grass": [
        "an overhead aerial image of pasture grass or open grassy field",
        "a remote sensing crop of green pasture with low vegetation and no tree crowns",
        "an orthomosaic patch of open grassland with smooth vegetation texture",
        "a nadir aerial view of pasture, not trees and not crop rows",
    ],
    "rough_rangeland_grass": [
        "a submeter overhead aerial image of rough rangeland grass with uneven tan green texture",
        "a remote sensing crop of natural grassland or prairie vegetation",
        "an orthomosaic patch of sparse rough grass and dry vegetation",
        "a nadir image of irregular grass cover without trees or roofs",
    ],
    "green_field_low_vegetation": [
        "an overhead aerial image of low green field vegetation, flat and non woody",
        "a remote sensing crop of green ground cover with no visible tree crowns",
        "an orthomosaic patch of low herbaceous vegetation",
        "a high resolution aerial crop of flat green field surface",
    ],

    "single_family_house_roof": [
        "a submeter overhead aerial image of a single family house roof with straight rectangular edges",
        "a nadir remote sensing crop of a residential rooftop surrounded by yard or driveway",
        "an orthomosaic patch showing a house roof, gutters, roof planes, and sharp corners",
        "an aerial image of a building roof with man made geometry and right angles",
    ],
    "rectangular_building_roof": [
        "an overhead aerial image of a rectangular building roof with straight edges and sharp corners",
        "a remote sensing crop centered on a flat man made rooftop footprint",
        "an orthomosaic patch of a building roof distinct from roads and ground",
        "a nadir image of a roof polygon with clean linear boundaries",
    ],
    "dark_shingle_roof": [
        "a submeter overhead image of a dark gray shingle roof on a building",
        "a satellite crop of a dark residential roof with rectangular roof planes",
        "an aerial image of a dark rooftop, not asphalt road, with building outline",
        "a nadir remote sensing crop of a dark house roof with straight edges",
    ],
    "light_roof_or_concrete_roof": [
        "a submeter overhead image of a light colored roof or white concrete roof",
        "a remote sensing crop of a pale building rooftop with rectangular footprint",
        "an aerial image of a light roof, not bare dirt, with sharp man made edges",
        "an orthomosaic patch showing a bright roof surface and building corners",
    ],
    "metal_roof_building": [
        "a nadir aerial image of a metal roof building or agricultural shed",
        "a remote sensing crop of a shiny or light metal rooftop with straight seams",
        "an overhead image of a farm building with metal roof panels",
        "an orthomosaic crop of a large rectangular metal roof structure",
    ],
    "small_shed_or_outbuilding": [
        "an overhead aerial image of a small shed or outbuilding roof",
        "a remote sensing crop of a small rectangular roof object in a yard",
        "an orthomosaic patch showing a garage, shed, or small roofed structure",
        "a nadir image of a compact man made structure with straight boundaries",
    ],
    "farm_or_industrial_structure": [
        "a submeter overhead image of a large farm or industrial building roof",
        "a satellite crop of a warehouse, barn, or industrial structure",
        "an aerial image of a large rectangular building with roof and paved surroundings",
        "a remote sensing crop of a non residential building structure",
    ],
    "damaged_or_broken_structure": [
        "an overhead aerial image of a damaged building roof with debris and broken edges",
        "a remote sensing crop of a collapsed or partially destroyed structure",
        "an orthomosaic patch showing roof damage, missing panels, or scattered building debris",
        "a nadir aerial crop of a storm damaged structure or broken roof",
    ],

    "asphalt_road": [
        "a submeter overhead aerial image of a dark asphalt road or street",
        "a remote sensing crop of a smooth dark paved road with linear shape",
        "an orthomosaic patch of asphalt pavement, not a rooftop",
        "a nadir aerial view of a road surface with lane-like geometry",
    ],
    "concrete_road": [
        "an overhead aerial image of a light concrete road or paved surface",
        "a remote sensing crop of pale concrete pavement with linear road shape",
        "an orthomosaic patch of light colored street pavement",
        "a nadir image of a concrete roadway or sidewalk-like paved strip",
    ],
    "gravel_road": [
        "a submeter overhead image of a gravel road with light gray rough texture",
        "a remote sensing crop of an unpaved gravel driveway or rural road",
        "an orthomosaic patch of pale gravel path with linear shape",
        "an aerial view of a light rough road surface, not a roof",
    ],
    "driveway_or_parking_area": [
        "an overhead aerial image of a driveway or parking pad next to buildings",
        "a remote sensing crop of paved parking surface or driveway connected to a structure",
        "an orthomosaic patch of man made pavement around buildings",
        "a nadir view of a driveway, parking lot, or paved apron",
    ],
    "linear_track_or_tire_path": [
        "an overhead aerial image of parallel tire tracks across grass or dirt",
        "a remote sensing crop of two narrow parallel lines from vehicle tracks",
        "an orthomosaic patch of linear tracks in a field or bare ground",
        "a nadir aerial view of unpaved vehicle tracks with regular parallel spacing",
    ],

    "bare_soil": [
        "a submeter overhead aerial image of exposed bare soil with brown texture",
        "a remote sensing crop of bare earth, not pavement and not roof",
        "an orthomosaic patch of brown soil surface without vegetation",
        "a nadir image of exposed ground with natural irregular texture",
    ],
    "tilled_dirt": [
        "an overhead aerial image of tilled dirt field with rough soil texture",
        "a remote sensing crop of plowed agricultural soil",
        "an orthomosaic patch of brown tilled earth with faint rows",
        "a nadir aerial view of disturbed bare field soil",
    ],
    "dry_bare_ground": [
        "a submeter overhead image of dry tan bare ground",
        "a remote sensing crop of pale dry earth with sparse vegetation",
        "an orthomosaic patch of dry exposed ground, not concrete",
        "a nadir aerial image of tan soil or dry dirt area",
    ],
    "crop_rows_on_bare_soil": [
        "an overhead aerial image of crop rows on bare dirt with regular parallel lines",
        "a remote sensing crop of agricultural rows with brown soil between lines",
        "an orthomosaic patch of field rows forming repeated linear pattern",
        "a nadir aerial view of cultivated crop rows in bare soil",
    ],
    "green_crop_field": [
        "an overhead aerial image of green agricultural crop rows",
        "a remote sensing crop of planted field with regular row structure",
        "an orthomosaic patch of green crops arranged in parallel lines",
        "a nadir aerial view of cultivated green field, not smooth lawn",
    ],

    "water": [
        "an overhead aerial image of water surface such as pond, stream, or flooded area",
        "a remote sensing crop of dark or reflective water",
        "an orthomosaic patch showing standing water with smooth texture",
        "a nadir aerial image of water, not shadow",
    ],
    "deep_shadow": [
        "an overhead aerial image of deep black shadow cast by trees or buildings",
        "a remote sensing crop of dark shadow with little visible texture",
        "an orthomosaic patch of shadowed ground, not water or asphalt",
        "a nadir aerial image of strong shadow adjacent to objects",
    ],
    "vehicle": [
        "an overhead aerial image of a vehicle or car",
        "a remote sensing crop of a parked car or truck",
        "an orthomosaic patch showing a small vehicle with rectangular shape",
        "a nadir aerial view of a car-sized object on road or driveway",
    ],
    "debris_or_rubble": [
        "an overhead aerial image of scattered debris or rubble",
        "a remote sensing crop of storm debris, broken material, or irregular wreckage",
        "an orthomosaic patch of debris field with chaotic texture",
        "a nadir aerial view of damaged scattered objects on ground",
    ],
    "unknown_mixed_landcover": [
        "an ambiguous overhead aerial image with mixed land cover",
        "a remote sensing crop that is unclear or contains several classes",
        "an orthomosaic patch that is not clearly trees grass road dirt roof or water",
        "a nadir aerial image of mixed background with no dominant class",
    ],
}


FINAL_CLASS_COLORS: dict[str, tuple[int, int, int]] = {
    "background": (0, 0, 0),
    "trees": (0, 135, 60),
    "grass": (130, 220, 80),
    "structures": (235, 60, 55),
    "roads": (80, 80, 80),
    "dirt": (185, 130, 75),
    "crops": (210, 180, 70),
    "water": (40, 110, 220),
    "shadow": (35, 35, 60),
    "vehicles": (255, 240, 90),
    "debris": (210, 80, 180),
    "other": (145, 145, 145),
}

FINAL_CLASS_TO_ID = {
    name: i for i, name in enumerate(("background",) + FINAL_CLASSES)
}

ID_TO_FINAL_CLASS = {
    v: k for k, v in FINAL_CLASS_TO_ID.items()
}


# ---------------------------------------------------------------------
# REMOTECLIP CLASSIFIER
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class RemoteCLIPSpec:
    model_name: str = "ViT-B-32"
    checkpoint_path: str | None = None
    hf_repo: str = "chendelong/RemoteCLIP"
    cache_dir: str = "checkpoints"
    device: str = "cpu"
    classes: tuple[str, ...] = DETAILED_CLASSES


class RemoteCLIPLandcoverClassifier:
    def __init__(self, spec: RemoteCLIPSpec) -> None:
        import open_clip
        from huggingface_hub import hf_hub_download

        self.spec = spec
        self.device = torch.device(spec.device)

        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            spec.model_name
        )
        self.tokenizer = open_clip.get_tokenizer(spec.model_name)

        if spec.checkpoint_path is None:
            checkpoint_path = hf_hub_download(
                repo_id=spec.hf_repo,
                filename=f"RemoteCLIP-{spec.model_name}.pt",
                cache_dir=spec.cache_dir,
            )
        else:
            checkpoint_path = spec.checkpoint_path

        ckpt = torch.load(checkpoint_path, map_location="cpu")

        if isinstance(ckpt, dict) and "state_dict" in ckpt:
            ckpt = ckpt["state_dict"]

        msg = self.model.load_state_dict(ckpt, strict=False)
        print("RemoteCLIP checkpoint loaded:", checkpoint_path)
        print("RemoteCLIP load_state_dict:", msg)

        self.model = self.model.to(self.device).eval()

        self.texts: list[str] = []
        self.text_to_class: list[str] = []

        for class_name in spec.classes:
            prompts = PROMPTS_BY_DETAILED_CLASS[class_name]
            for prompt in prompts:
                self.texts.append(prompt)
                self.text_to_class.append(class_name)

        with torch.no_grad():
            text_tokens = self.tokenizer(self.texts).to(self.device)
            text_features = self.model.encode_text(text_tokens)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)

        self.text_features = text_features

        self.prompt_indices_by_class: dict[str, list[int]] = {
            class_name: [
                i for i, mapped_class in enumerate(self.text_to_class)
                if mapped_class == class_name
            ]
            for class_name in self.spec.classes
        }

    def classify_pil(self, image: Image.Image) -> dict[str, float]:
        """
        Return detailed class probabilities.

        Important:
          We average prompt logits per class before softmax.
          This avoids biasing classes that have more prompts.
        """
        image = image.convert("RGB")
        image_tensor = self.preprocess(image).unsqueeze(0).to(self.device)

        with torch.no_grad():
            image_features = self.model.encode_image(image_tensor)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)

            prompt_logits = (100.0 * image_features @ self.text_features.T).squeeze(0)

            class_logits = []
            for class_name in self.spec.classes:
                idxs = self.prompt_indices_by_class[class_name]
                class_logits.append(prompt_logits[idxs].mean())

            class_logits_tensor = torch.stack(class_logits)
            class_probs = class_logits_tensor.softmax(dim=0).detach().cpu().numpy()

        return {
            class_name: float(prob)
            for class_name, prob in zip(self.spec.classes, class_probs)
        }


def collapse_detailed_scores_to_final(
    detailed_scores: dict[str, float],
) -> dict[str, float]:
    final = {name: 0.0 for name in FINAL_CLASSES}

    for detailed_class, score in detailed_scores.items():
        final_class = DETAILED_TO_FINAL.get(detailed_class, "other")
        final[final_class] += float(score)

    total = sum(final.values())
    if total > 0:
        final = {k: float(v / total) for k, v in final.items()}

    return final


def prefer_structures_if_close(
    final_scores: dict[str, float],
    *,
    margin: float = 0.08,
    min_structure_score: float = 0.22,
) -> dict[str, float]:
    """
    Practical bias:
      If RemoteCLIP says 'roads/dirt/other' slightly above structures, but
      structures is close, prefer structures.

    This helps rooftops that look like pavement.
    """
    scores = dict(final_scores)

    top_class = max(scores, key=scores.get)
    top_score = float(scores[top_class])
    structure_score = float(scores.get("structures", 0.0))

    if (
        top_class in {"roads", "dirt", "other", "shadow"}
        and structure_score >= min_structure_score
        and top_score - structure_score <= margin
    ):
        scores["structures"] = top_score + 0.001
        scores[top_class] = max(0.0, structure_score - 0.001)

    total = sum(scores.values())
    if total > 0:
        scores = {k: float(v / total) for k, v in scores.items()}

    return scores


# ---------------------------------------------------------------------
# CROPS AND CLASSIFICATION
# ---------------------------------------------------------------------


def bbox_from_mask(mask: np.ndarray, pad: int = 8) -> tuple[int, int, int, int] | None:
    ys, xs = np.where(mask)

    if xs.size == 0 or ys.size == 0:
        return None

    h, w = mask.shape

    left = max(0, int(xs.min()) - pad)
    right = min(w, int(xs.max()) + pad + 1)
    upper = max(0, int(ys.min()) - pad)
    lower = min(h, int(ys.max()) + pad + 1)

    return left, upper, right, lower


def object_context_crop(
    rgb: np.ndarray,
    instance_mask: np.ndarray,
    object_id: int,
    *,
    pad: int = 48,
) -> Image.Image | None:
    obj_mask = instance_mask == object_id
    bbox = bbox_from_mask(obj_mask, pad=pad)

    if bbox is None:
        return None

    left, upper, right, lower = bbox
    return Image.fromarray(rgb[upper:lower, left:right].copy())


def masked_object_crop(
    rgb: np.ndarray,
    instance_mask: np.ndarray,
    object_id: int,
    *,
    pad: int = 24,
    background_value: int = 128,
) -> Image.Image | None:
    obj_mask = instance_mask == object_id
    bbox = bbox_from_mask(obj_mask, pad=pad)

    if bbox is None:
        return None

    left, upper, right, lower = bbox

    rgb_crop = rgb[upper:lower, left:right].copy()
    mask_crop = obj_mask[upper:lower, left:right]

    rgb_crop[~mask_crop] = background_value

    return Image.fromarray(rgb_crop)


def get_object_crop(
    rgb: np.ndarray,
    mask: np.ndarray,
    object_id: int,
    *,
    crop_mode: CropMode,
) -> Image.Image | None:
    if crop_mode == "context":
        return object_context_crop(rgb, mask, object_id, pad=56)

    if crop_mode == "masked":
        return masked_object_crop(rgb, mask, object_id, pad=28)

    raise ValueError(f"unknown crop_mode: {crop_mode}")


def save_object_crop(
    crop: Image.Image,
    out_dir: str | Path,
    stem: str,
    object_id: int,
    predicted_final_class: str,
    predicted_detailed_class: str,
    score: float,
) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    safe_score = f"{score:.3f}".replace(".", "p")
    crop.save(
        out_dir
        / f"{stem}_obj{object_id:04d}_{predicted_final_class}_{predicted_detailed_class}_{safe_score}.png"
    )


def classify_sam_landcover_remoteclip(
    tile: np.ndarray,
    sam_result: SamGeoTileMaskResult,
    *,
    sam_spec: SamGeoTileMaskSpec,
    classifier: RemoteCLIPLandcoverClassifier,
    crop_mode: CropMode = "context",
    min_object_area_fraction: float = 0.0002,
    mostly_threshold: float = 0.60,
    mixed_second_threshold: float = 0.25,
    save_crops_dir: str | Path | None = None,
    stem: str = "tile",
) -> dict[str, Any]:
    rgb = tile_to_rgb_uint8(
        tile,
        layout=sam_spec.layout,
        rgb_bands=sam_spec.rgb_bands,
        p_low=sam_spec.percentile_low,
        p_high=sam_spec.percentile_high,
    )

    mask = np.asarray(sam_result.mask)

    if mask.ndim == 3:
        mask = mask[..., 0]

    h, w = mask.shape
    tile_area = h * w

    object_ids = np.unique(mask)
    object_ids = object_ids[object_ids != 0]

    weighted_final_scores = {name: 0.0 for name in FINAL_CLASSES}
    weighted_detailed_scores = {name: 0.0 for name in DETAILED_CLASSES}
    assigned_area_fraction = {name: 0.0 for name in FINAL_CLASSES}
    objects: list[dict[str, Any]] = []

    for object_id in object_ids:
        obj_mask = mask == object_id
        obj_area = int(obj_mask.sum())
        obj_area_fraction = float(obj_area / tile_area)

        if obj_area_fraction < min_object_area_fraction:
            continue

        crop = get_object_crop(rgb, mask, int(object_id), crop_mode=crop_mode)

        if crop is None:
            continue

        detailed_scores = classifier.classify_pil(crop)
        final_scores = collapse_detailed_scores_to_final(detailed_scores)
        final_scores = prefer_structures_if_close(final_scores)

        predicted_detailed_class = max(detailed_scores, key=detailed_scores.get)
        predicted_final_class = max(final_scores, key=final_scores.get)
        predicted_final_score = float(final_scores[predicted_final_class])
        predicted_detailed_score = float(detailed_scores[predicted_detailed_class])

        for class_name, score in final_scores.items():
            weighted_final_scores[class_name] += obj_area_fraction * float(score)

        for class_name, score in detailed_scores.items():
            weighted_detailed_scores[class_name] += obj_area_fraction * float(score)

        assigned_area_fraction[predicted_final_class] += obj_area_fraction

        if save_crops_dir is not None:
            save_object_crop(
                crop,
                save_crops_dir,
                stem,
                int(object_id),
                predicted_final_class,
                predicted_detailed_class,
                predicted_final_score,
            )

        objects.append(
            {
                "object_id": int(object_id),
                "area_pixels": obj_area,
                "area_fraction": obj_area_fraction,
                "predicted_final_class": predicted_final_class,
                "predicted_final_score": predicted_final_score,
                "predicted_detailed_class": predicted_detailed_class,
                "predicted_detailed_score": predicted_detailed_score,
                "final_scores": final_scores,
                "detailed_scores": detailed_scores,
            }
        )

    total_final_score = sum(weighted_final_scores.values())

    if total_final_score > 0:
        normalized_final_scores = {
            k: float(v / total_final_score)
            for k, v in weighted_final_scores.items()
        }
    else:
        normalized_final_scores = {
            k: 0.0 for k in weighted_final_scores
        }

    total_detailed_score = sum(weighted_detailed_scores.values())

    if total_detailed_score > 0:
        normalized_detailed_scores = {
            k: float(v / total_detailed_score)
            for k, v in weighted_detailed_scores.items()
        }
    else:
        normalized_detailed_scores = {
            k: 0.0 for k in weighted_detailed_scores
        }

    ranked = sorted(
        normalized_final_scores.items(),
        key=lambda kv: kv[1],
        reverse=True,
    )

    if ranked:
        top_class, top_fraction = ranked[0]
        second_class, second_fraction = ranked[1] if len(ranked) > 1 else ("none", 0.0)
    else:
        top_class, top_fraction = "unknown", 0.0
        second_class, second_fraction = "none", 0.0

    mixed = (
        top_fraction < mostly_threshold
        or second_fraction >= mixed_second_threshold
    )

    dominant = "mixed" if mixed else top_class

    return {
        "model_task": "sam_objects_remoteclip_detailed_landcover",
        "model": {
            "name": "RemoteCLIP",
            "openclip_model_name": classifier.spec.model_name,
            "hf_repo": classifier.spec.hf_repo,
        },
        "crop_mode": crop_mode,
        "final_classes": list(FINAL_CLASSES),
        "detailed_classes": list(DETAILED_CLASSES),
        "dominant": dominant,
        "mixed": bool(mixed),
        "top_class": top_class,
        "top_fraction": float(top_fraction),
        "second_class": second_class,
        "second_fraction": float(second_fraction),
        "normalized_final_scores": normalized_final_scores,
        "normalized_detailed_scores": normalized_detailed_scores,
        "weighted_final_scores": weighted_final_scores,
        "assigned_area_fraction": assigned_area_fraction,
        "object_count_total": int(len(object_ids)),
        "object_count_classified": int(len(objects)),
        "thresholds": {
            "min_object_area_fraction": min_object_area_fraction,
            "mostly_threshold": mostly_threshold,
            "mixed_second_threshold": mixed_second_threshold,
        },
        "objects": objects,
    }


# ---------------------------------------------------------------------
# VISUALIZATION
# ---------------------------------------------------------------------


def colorize_instance_mask(mask: np.ndarray, seed: int = 17) -> np.ndarray:
    mask = np.asarray(mask)

    if mask.ndim == 3:
        mask = mask[..., 0]

    h, w = mask.shape
    out = np.zeros((h, w, 3), dtype=np.uint8)

    object_ids = np.unique(mask)
    object_ids = object_ids[object_ids != 0]

    rng = np.random.default_rng(seed)

    for object_id in object_ids:
        color = rng.integers(40, 255, size=3, dtype=np.uint8)
        out[mask == object_id] = color

    return out


def make_mask_overlay(
    rgb: np.ndarray,
    mask: np.ndarray,
    alpha: float = 0.45,
    seed: int = 17,
) -> np.ndarray:
    rgb = np.asarray(rgb, dtype=np.uint8)
    colored = colorize_instance_mask(mask, seed=seed)

    foreground = mask > 0

    overlay = rgb.copy().astype(np.float32)
    overlay[foreground] = (
        (1.0 - alpha) * overlay[foreground]
        + alpha * colored[foreground].astype(np.float32)
    )

    return np.clip(overlay, 0, 255).astype(np.uint8)


def final_class_mask_from_sam_objects(
    instance_mask: np.ndarray,
    landcover: dict[str, Any],
    *,
    min_score: float = 0.0,
) -> np.ndarray:
    mask = np.asarray(instance_mask)

    if mask.ndim == 3:
        mask = mask[..., 0]

    class_mask = np.zeros(mask.shape, dtype=np.uint8)

    for obj in landcover.get("objects", []):
        object_id = int(obj["object_id"])
        final_class = str(obj["predicted_final_class"])
        score = float(obj.get("predicted_final_score", 0.0))

        if score < min_score:
            final_class = "other"

        class_id = FINAL_CLASS_TO_ID.get(final_class, FINAL_CLASS_TO_ID["other"])
        class_mask[mask == object_id] = class_id

    return class_mask


def colorize_final_class_mask(class_mask: np.ndarray) -> np.ndarray:
    class_mask = np.asarray(class_mask)

    h, w = class_mask.shape
    out = np.zeros((h, w, 3), dtype=np.uint8)

    for class_id, class_name in ID_TO_FINAL_CLASS.items():
        color = FINAL_CLASS_COLORS[class_name]
        out[class_mask == class_id] = color

    return out


def make_final_class_overlay(
    rgb: np.ndarray,
    class_mask: np.ndarray,
    *,
    alpha: float = 0.45,
) -> np.ndarray:
    rgb = np.asarray(rgb, dtype=np.uint8)
    color_mask = colorize_final_class_mask(class_mask)

    foreground = class_mask > 0

    overlay = rgb.copy().astype(np.float32)
    overlay[foreground] = (
        (1.0 - alpha) * overlay[foreground]
        + alpha * color_mask[foreground].astype(np.float32)
    )

    return np.clip(overlay, 0, 255).astype(np.uint8)


def make_final_class_legend(out_path: str | Path) -> None:
    from PIL import ImageDraw

    rows = [(name, FINAL_CLASS_COLORS[name]) for name in FINAL_CLASSES]

    swatch = 28
    width = 360
    height = swatch * len(rows)

    img = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    for i, (name, color) in enumerate(rows):
        y0 = i * swatch
        y1 = y0 + swatch
        draw.rectangle([0, y0, swatch, y1], fill=color)
        draw.text((swatch + 10, y0 + 7), name, fill=(0, 0, 0))

    img.save(out_path)


def save_annotation_bundle(
    tile: np.ndarray,
    result: SamGeoTileMaskResult,
    out_dir: str | Path,
    stem: str,
    spec: SamGeoTileMaskSpec,
) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rgb = tile_to_rgb_uint8(
        tile,
        layout=spec.layout,
        rgb_bands=spec.rgb_bands,
        p_low=spec.percentile_low,
        p_high=spec.percentile_high,
    )

    instance_vis = colorize_instance_mask(result.mask)
    overlay = make_mask_overlay(rgb, result.mask)

    Image.fromarray(rgb).save(out_dir / f"{stem}_rgb.png")
    Image.fromarray(instance_vis).save(out_dir / f"{stem}_sam_instances.png")
    Image.fromarray(overlay).save(out_dir / f"{stem}_sam_overlay.png")

    np.save(out_dir / f"{stem}_sam_mask.npy", result.mask)

    (out_dir / f"{stem}_sam_metadata.json").write_text(
        json.dumps(result.metadata, indent=2),
        encoding="utf-8",
    )


def save_final_class_overlay_bundle(
    tile: np.ndarray,
    sam_result: SamGeoTileMaskResult,
    landcover: dict[str, Any],
    out_dir: str | Path,
    stem: str,
    spec: SamGeoTileMaskSpec,
    *,
    min_score: float = 0.0,
    alpha: float = 0.45,
) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rgb = tile_to_rgb_uint8(
        tile,
        layout=spec.layout,
        rgb_bands=spec.rgb_bands,
        p_low=spec.percentile_low,
        p_high=spec.percentile_high,
    )

    class_mask = final_class_mask_from_sam_objects(
        sam_result.mask,
        landcover,
        min_score=min_score,
    )

    class_mask_rgb = colorize_final_class_mask(class_mask)
    class_overlay = make_final_class_overlay(rgb, class_mask, alpha=alpha)

    np.save(out_dir / f"{stem}_final_class_mask.npy", class_mask)
    Image.fromarray(class_mask_rgb).save(out_dir / f"{stem}_final_class_mask.png")
    Image.fromarray(class_overlay).save(out_dir / f"{stem}_final_class_overlay.png")

    make_final_class_legend(out_dir / "final_class_legend.png")


# ---------------------------------------------------------------------
# INPUT LOADERS
# ---------------------------------------------------------------------


def load_npy_member_from_tar(tar_path: str | Path, member_name: str) -> np.ndarray:
    tar_path = Path(tar_path)

    with tarfile.open(tar_path, "r") as tar:
        f = tar.extractfile(member_name)

        if f is None:
            raise FileNotFoundError(
                f"Could not find {member_name} inside {tar_path}"
            )

        return np.load(BytesIO(f.read()), allow_pickle=False)


def load_tile_from_args(args: argparse.Namespace) -> tuple[np.ndarray, str]:
    if args.npy is not None:
        npy_path = Path(args.npy)
        tile = np.load(npy_path, allow_pickle=False)
        return tile, npy_path.stem

    if args.tar is not None and args.member is not None:
        tile = load_npy_member_from_tar(args.tar, args.member)
        return tile, Path(args.member).stem

    raise ValueError("provide either --npy PATH or --tar PATH --member NAME")


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument("--npy", default=None)
    parser.add_argument("--tar", default=None)
    parser.add_argument("--member", default=None)

    parser.add_argument("--sam-checkpoint", default="/home/rhea/B/sam_vit_b_01ec64.pth")
    parser.add_argument("--sam-model-type", default="vit_b")
    parser.add_argument("--device", default="cpu")

    parser.add_argument("--remoteclip-model", default="ViT-B-32")
    parser.add_argument("--remoteclip-checkpoint", default=None)
    parser.add_argument("--remoteclip-cache", default="/home/rhea/B/checkpoints")

    parser.add_argument("--out-dir", default="annotation_exports")
    parser.add_argument("--save-crops", action="store_true")

    parser.add_argument("--crop-mode", choices=["context", "masked"], default="context")

    parser.add_argument("--min-object-area", type=float, default=0.0002)
    parser.add_argument("--mostly-threshold", type=float, default=0.60)
    parser.add_argument("--mixed-second-threshold", type=float, default=0.25)

    parser.add_argument("--overlay-min-score", type=float, default=0.18)
    parser.add_argument("--overlay-alpha", type=float, default=0.45)

    args = parser.parse_args()

    tile, stem = load_tile_from_args(args)

    print("tile:", stem)
    print("shape:", tile.shape)
    print("dtype:", tile.dtype)
    print("min/max:", np.nanmin(tile), np.nanmax(tile))
    print("nonzero:", np.count_nonzero(tile), "of", tile.size)

    sam_spec = SamGeoTileMaskSpec(
        model_type=args.sam_model_type,
        checkpoint=args.sam_checkpoint,
        device=args.device,
        layout="chw",
        rgb_bands=(0, 1, 2),
        mask_mode="instance",
    )

    masker = SamGeoTileMasker(sam_spec)
    sam_result = masker.run(tile, tile_id=stem)

    remoteclip = RemoteCLIPLandcoverClassifier(
        RemoteCLIPSpec(
            model_name=args.remoteclip_model,
            checkpoint_path=args.remoteclip_checkpoint,
            cache_dir=args.remoteclip_cache,
            device=args.device,
        )
    )

    crops_dir = Path(args.out_dir) / "object_crops" if args.save_crops else None

    landcover = classify_sam_landcover_remoteclip(
        tile,
        sam_result,
        sam_spec=sam_spec,
        classifier=remoteclip,
        crop_mode=args.crop_mode,
        min_object_area_fraction=args.min_object_area,
        mostly_threshold=args.mostly_threshold,
        mixed_second_threshold=args.mixed_second_threshold,
        save_crops_dir=crops_dir,
        stem=stem,
    )

    sam_result.metadata["landcover"] = landcover

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    save_annotation_bundle(
        tile=tile,
        result=sam_result,
        out_dir=out_dir,
        stem=stem,
        spec=sam_spec,
    )

    save_final_class_overlay_bundle(
        tile=tile,
        sam_result=sam_result,
        landcover=landcover,
        out_dir=out_dir,
        stem=stem,
        spec=sam_spec,
        min_score=args.overlay_min_score,
        alpha=args.overlay_alpha,
    )

    (out_dir / f"{stem}_sam_remoteclip_metadata.json").write_text(
        json.dumps(sam_result.metadata, indent=2),
        encoding="utf-8",
    )

    print("\nLANDCOVER")
    print(json.dumps(landcover, indent=2))


if __name__ == "__main__":
    main()
