
"""
Commented RemoteCLIP semantic classifier for Whirlwind tiles.

This version keeps the same basic design as your current wrapper:

1. Convert a raster tile array into an RGB uint8 image.
2. Encode the image with RemoteCLIP.
3. Compare that image embedding against text prompt embeddings.
4. Average prompts into detailed class scores.
5. Collapse detailed scores into final class scores.
6. Convert the scores into a SemanticLabel with a bucket name.

Important fix versus the uploaded version:
    FINAL_CLASSES is imported here, because _collapse_to_final() needs it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal, Sequence

import numpy as np
from PIL import Image

import torch
import open_clip
from huggingface_hub import hf_hub_download

from whirlwind.adapters.arrays.scale import scale_to_uint8
from whirlwind.bridges.specs.semclass import SCSpec, ArrayLayout
from whirlwind.prompts.detailed_classes import (
    DETAILED_CLASSES,
    DETAILED_TO_FINAL,
    FINAL_CLASSES,  # Needed by _collapse_to_final().
    PROMPTS_BY_DETAILED_CLASS,
)


@dataclass(frozen=True)
class SemanticLabel:
    """
    Final semantic result for one tile.

    This is intentionally small enough to store in the tile JSON metadata.

    bucket
        Name used by shard writing, for example:
            mostly_structures
            mostly_trees
            hybrid_structures_roads
            mixed

    dominant
        The class you should treat as the main class. This is "mixed" when
        confidence is not high enough for a clean single-class label.

    mixed
        True when the tile is not confidently one dominant final class.

    top_class / top_score
        Highest-scoring final class and its probability-like score.

    second_class / second_score
        Second-highest final class and its score. This is useful for hybrid
        buckets and for debugging ambiguous tiles.

    final_scores
        Scores after detailed classes are collapsed into your coarse classes:
        structures, roads, tracks, trees, grass, dirt, crops, etc.

    detailed_scores
        Scores for the detailed RemoteCLIP prompt classes before collapsing.

    thresholds / bucket_mode
        Copied from SCSpec so every tile records the rules that produced its
        label. This matters because changing thresholds later changes labels.
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
        """
        Return a plain dict suitable for JSON serialization.

        dataclasses.asdict() recursively converts nested dataclasses too. Here
        the nested values are normal dicts/floats, so it mostly just saves you
        from hand-writing every field name.
        """
        return asdict(self)


def resolve_layout(arr: np.ndarray, layout: ArrayLayout) -> Literal["chw", "hwc"]:
    """
    Decide whether a 3D tile is channel-first or channel-last.

    Rasterio usually gives CHW:
        (bands, height, width)

    Image libraries usually use HWC:
        (height, width, channels)

    layout can be explicit:
        "chw" -> trust that tile is bands/height/width
        "hwc" -> trust that tile is height/width/bands

    Or layout can be "auto", in which case this function guesses from shape.
    The assumption is that the channel dimension is small, usually 1-16, while
    height and width are much larger.
    """
    if layout in ("chw", "hwc"):
        return layout

    if arr.ndim != 3:
        raise ValueError("layout='auto' only applies to 3D arrays")

    # Looks like CHW: small band count first, then large image dimensions.
    if arr.shape[0] <= 16 and arr.shape[1] > 16 and arr.shape[2] > 16:
        return "chw"

    # Looks like HWC: large image dimensions first, small channel count last.
    if arr.shape[2] <= 16 and arr.shape[0] > 16 and arr.shape[1] > 16:
        return "hwc"

    # Ambiguous shapes should fail loudly rather than silently misclassify.
    raise ValueError(f"could not infer tile layout from shape {arr.shape}")


def tile_to_rgb_uint8(
    tile: np.ndarray,
    *,
    layout: ArrayLayout,
    rgb_bands: tuple[int, int, int],
    p_low: float,
    p_high: float,
) -> np.ndarray:
    """
    Convert a raster tile into an HWC RGB uint8 image for RemoteCLIP.

    RemoteCLIP/OpenCLIP expects a PIL RGB image. Your raster tiles might be:
        2D: grayscale/single-band tile
        3D CHW: rasterio-style multi-band tile
        3D HWC: image-style multi-band tile

    This function:
        - selects 3 bands,
        - moves them into HWC order,
        - percentile-scales values into uint8 [0, 255].

    rgb_bands is zero-based. For a normal RGB raster, use (0, 1, 2).
    For BGR or multispectral rasters, change this in SCSpec.
    """
    arr = np.asarray(tile)

    if arr.ndim == 2:
        # Single-band tile. Repeat the band into R/G/B so PIL sees RGB.
        rgb_float = np.stack([arr, arr, arr], axis=-1)

    elif arr.ndim == 3:
        resolved = resolve_layout(arr, layout)

        if resolved == "chw":
            # CHW -> select bands along axis 0, then transpose to HWC.
            max_band = arr.shape[0] - 1

            # Clamp requested bands into the valid range. This prevents a crash
            # if a 2-band raster is accidentally used with rgb_bands=(0,1,2).
            bands = [min(max(b, 0), max_band) for b in rgb_bands]

            # After this, shape is (height, width, 3).
            rgb_float = np.transpose(arr[bands, :, :], (1, 2, 0))

        else:
            # HWC -> select bands along the last axis.
            max_band = arr.shape[2] - 1
            bands = [min(max(b, 0), max_band) for b in rgb_bands]
            rgb_float = arr[:, :, bands]

    else:
        raise ValueError(f"expected 2D or 3D tile array, got {arr.shape}")

    # Convert arbitrary raster dtype/range into uint8 display values.
    # This should use your existing scaling helper, which likely handles
    # percentiles and clipping better than a naive min/max conversion.
    return scale_to_uint8(rgb_float, p_low=p_low, p_high=p_high)


class SemanticClassifier:
    """
    Whole-tile semantic classifier wrapper around RemoteCLIP.

    The classifier is zero-shot: it does not train on your labels. Instead, it
    compares each tile image against text prompts like "overhead aerial image of
    a building roof" or "parallel tire tracks across grass or dirt".

    Input:
        A numpy tile array, usually CHW from rasterio.

    Output:
        A SemanticLabel containing class scores and a shard bucket name.
    """

    def __init__(self, spec: SCSpec) -> None:
        """
        Load RemoteCLIP once and precompute text embeddings once.

        Expensive work belongs here:
            - model creation,
            - checkpoint loading,
            - tokenizer creation,
            - prompt tokenization,
            - text embedding computation.

        classify_tile() should only do per-tile work.
        """
        self.spec = spec
        self.device = torch.device(spec.device)

        # Build the OpenCLIP model and the image preprocessing transform.
        # create_model_and_transforms returns:
        #   model, train_preprocess, val_preprocess
        # We only need the model and inference preprocess.
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            spec.model_name
        )

        # Tokenizer converts prompt strings into token IDs the text encoder can read.
        self.tokenizer = open_clip.get_tokenizer(spec.model_name)

        # Load the RemoteCLIP weights. If the user passed an explicit checkpoint,
        # use it. Otherwise download from the configured HuggingFace repo/cache.
        if spec.checkpoint_path is None:
            checkpoint_path = hf_hub_download(
                repo_id=spec.hf_repo,
                filename=f"RemoteCLIP-{spec.model_name}.pt",
                cache_dir=spec.cache_dir,
            )
        else:
            checkpoint_path = spec.checkpoint_path

        # Load onto CPU first so the file can be read regardless of target device.
        ckpt = torch.load(checkpoint_path, map_location="cpu")

        # Some checkpoints wrap model weights under "state_dict".
        if isinstance(ckpt, dict) and "state_dict" in ckpt:
            ckpt = ckpt["state_dict"]

        # strict=False makes loading tolerant of harmless checkpoint/model key
        # differences. If classifications look wrong, print missing/unexpected
        # keys here during debugging.
        self.model.load_state_dict(ckpt, strict=False)

        # Move model to CPU/GPU and switch off training-time behavior.
        self.model = self.model.to(self.device).eval()

        # Detailed classes are the fine-grained text categories, for example:
        #   dark_shingle_roof, gravel_road, crop_rows_on_bare_soil.
        self.detailed_classes = DETAILED_CLASSES

        # Flat list of every prompt string, across every detailed class.
        self.texts: list[str] = []

        # Parallel list mapping each prompt back to its detailed class.
        # Example:
        #   texts[17] = "an overhead aerial image of a gravel road..."
        #   text_to_class[17] = "gravel_road"
        self.text_to_class: list[str] = []

        # Build the flat prompt table from PROMPTS_BY_DETAILED_CLASS.
        for class_name in self.detailed_classes:
            prompts = PROMPTS_BY_DETAILED_CLASS[class_name]
            for prompt in prompts:
                self.texts.append(prompt)
                self.text_to_class.append(class_name)

        # Text prompts do not change from tile to tile, so encode them once.
        with torch.no_grad():
            text_tokens = self.tokenizer(self.texts).to(self.device)
            text_features = self.model.encode_text(text_tokens)

            # Normalize to unit length so dot product becomes cosine similarity.
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)

        self.text_features = text_features

        # For each detailed class, remember which prompt indices belong to it.
        # This lets _classify_image() average prompt scores into one class score.
        self.prompt_indices_by_class: dict[str, list[int]] = {
            class_name: [
                i
                for i, mapped_class in enumerate(self.text_to_class)
                if mapped_class == class_name
            ]
            for class_name in self.detailed_classes
        }

    def classify_tile(self, tile: np.ndarray) -> SemanticLabel:
        """
        Classify one raster tile and return a SemanticLabel.

        This is the main method you call from tessellation before writing the
        tile into a shard.
        """
        # Convert raster array into a PIL-compatible RGB uint8 image.
        rgb = tile_to_rgb_uint8(
            tile,
            layout=self.spec.layout,
            rgb_bands=self.spec.rgb_bands,
            p_low=self.spec.percentile_low,
            p_high=self.spec.percentile_high,
        )

        # PIL image is what the OpenCLIP preprocess transform expects.
        image = Image.fromarray(rgb).convert("RGB")

        # Fine-grained class scores from RemoteCLIP text prompts.
        detailed_scores = self._classify_image(image)

        # Collapse fine-grained classes into your final buckets/classes.
        final_scores = self._collapse_to_final(detailed_scores)

        # Optional heuristic: if structures are close to the top score, prefer
        # structures over road/dirt/shadow/mixed. This helps with roofs being
        # confused with pavement, dirt pads, or deep shadow.
        if self.spec.prefer_structures:
            final_scores = self._prefer_structures_if_close(final_scores)

        # Convert scores into a durable label object with bucket name.
        return self._label_from_scores(
            final_scores=final_scores,
            detailed_scores=detailed_scores,
        )

    def classify_tiles(self, tiles: Sequence[np.ndarray]) -> list[SemanticLabel]:
        """
        Simple multi-tile API.

        This currently loops one tile at a time. It is useful as a stable API,
        but it is not a true GPU batch implementation yet.
        """
        return [self.classify_tile(tile) for tile in tiles]

    def _classify_image(self, image: Image.Image) -> dict[str, float]:
        """
        Compare one image against all text prompts.

        Returns detailed class scores that sum to roughly 1.0 because the final
        step applies softmax over detailed classes.
        """
        # Apply OpenCLIP preprocessing: resize/crop, convert to tensor, normalize.
        # unsqueeze(0) adds a batch dimension: C,H,W -> 1,C,H,W.
        image_tensor = self.preprocess(image).unsqueeze(0).to(self.device)

        with torch.no_grad():
            # Encode image into the same embedding space as the text prompts.
            image_features = self.model.encode_image(image_tensor)

            # Normalize so image/text dot product behaves like cosine similarity.
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)

            # Similarity between the image and every prompt.
            # Shape: (num_prompts,)
            # The 100.0 scale sharpens softmax probabilities. This mirrors common
            # CLIP inference practice; you can later replace it with model.logit_scale
            # if you want to use the model's learned logit scale.
            prompt_logits = (100.0 * image_features @ self.text_features.T).squeeze(0)

            # Convert many prompt scores into one score per detailed class by
            # averaging all prompts assigned to that class.
            class_logits = []
            for class_name in self.detailed_classes:
                idxs = self.prompt_indices_by_class[class_name]
                class_logits.append(prompt_logits[idxs].mean())

            # Turn class logits into probabilities over detailed classes.
            class_logits_tensor = torch.stack(class_logits)
            class_probs = class_logits_tensor.softmax(dim=0).detach().cpu().numpy()

        return {
            class_name: float(prob)
            for class_name, prob in zip(self.detailed_classes, class_probs)
        }

    def _collapse_to_final(self, detailed_scores: dict[str, float]) -> dict[str, float]:
        """
        Collapse detailed scores into final Whirlwind land-cover classes.

        Example:
            single_family_house_roof -> structures
            dark_shingle_roof       -> structures
            metal_roof_building     -> structures

        Their probabilities are summed into final_scores["structures"].
        """
        # Start every final class at 0.0 so the output always has stable keys.
        scores = {name: 0.0 for name in FINAL_CLASSES}

        for detailed_class, score in detailed_scores.items():
            # Unknown detailed classes fall into mixed rather than crashing.
            final_class = DETAILED_TO_FINAL.get(detailed_class, "mixed")
            scores[final_class] += float(score)

        # Re-normalize after summing. This guards against floating point drift or
        # missing classes and makes final_scores easier to interpret.
        total = sum(scores.values())
        if total > 0:
            scores = {k: float(v / total) for k, v in scores.items()}

        return scores

    def _prefer_structures_if_close(
        self,
        final_scores: dict[str, float],
    ) -> dict[str, float]:
        """
        Heuristic correction for roof-like tiles.

        Remote-sensing roofs can look like roads, dirt pads, white concrete, or
        shadows. This rule says: if structures are close enough to the current
        winner and above a minimum score, let structures win.

        This is intentionally narrow. It only applies when the current winner is
        one of the common roof-confuser classes.
        """
        scores = dict(final_scores)

        top_class = max(scores, key=scores.get)
        top_score = float(scores[top_class])
        structure_score = float(scores.get("structures", 0.0))

        if (
            top_class in {"roads", "tracks", "dirt", "shadow", "mixed"}
            and structure_score >= self.spec.min_structure_score
            and top_score - structure_score <= self.spec.structure_margin
        ):
            # Small swap: make structures slightly larger than the original top.
            scores["structures"] = top_score + 0.001
            scores[top_class] = max(0.0, structure_score - 0.001)

        # Normalize again after manual adjustment.
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
        """
        Convert final class scores into a SemanticLabel.

        Main idea:
            - If the top class is strong enough and the second class is weak,
              call the tile "mostly_<top_class>".
            - If not, call it mixed or hybrid depending on bucket_mode.
        """
        ranked = sorted(final_scores.items(), key=lambda kv: kv[1], reverse=True)

        top_class, top_score = ranked[0]
        second_class, second_score = ranked[1] if len(ranked) > 1 else ("none", 0.0)

        # A tile is mixed if:
        #   1. the winner is below mostly_threshold, OR
        #   2. the second class is high enough to matter.
        mixed = (
            top_score < self.spec.mostly_threshold
            or second_score >= self.spec.hybrid_second_threshold
        )

        bucket = self._bucket_name(
            top_class=top_class,
            top_score=float(top_score),
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
        top_score: float,
        second_class: str,
        second_score: float,
        mixed: bool,
    ) -> str:
        """
        Pick the directory/shard bucket name for a tile.

        Bucket examples:
            mostly_structures
            mostly_trees
            mixed
            hybrid_structures_roads

        top_score is accepted here for readability/debug symmetry, even though
        the current rules do not need it directly.
        """
        _ = top_score  # Keeps the argument intentional even if unused for now.

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
