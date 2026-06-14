
from pathlib import Path
from typing import Sequence

import numpy as np
from PIL import Image

import torch
import open_clip
from huggingface_hub import hf_hub_download

from whirlwind.bridges.specs.semclass import SCSpec 
from whirlwind.prompts.detailed_classes import (
        DETAILED_CLASSES, PROMPTS_BY_DETAILED_CLASS, 
        FINAL_CLASSES, DETAILED_TO_FINAL
        )

from whirlwind.adapters.display.colorcontrols import tile_to_rgb_uint8
from whirlwind.adapters.label.semantic_labels import SemanticLabel, BinScore
from whirlwind.domain.tile import Tile

class SemanticClassifier:
    """ 
        used to create labels according to RemoteCLIP classification, with classes 
        provided by prompt/classes 
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
            final_class = DETAILED_TO_FINAL.get(detailed_class, "review")
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
            top_class in {"roads", "tracks", "dirt", "shadow", "review"}
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
            

        top_bin = BinScore(name = top_class, score=top_score) 
        second_bin = BinScore(name=second_class, score=second_score) 

        mixed = (
            top_score < self.spec.mostly_threshold
            or second_score >= self.spec.hybrid_second_threshold
        )

        bucket = self._bucket_name(
                top_bin = top_bin,
                second_bin=second_bin, 
                mixed=mixed
            )


        dominant = "review" if mixed else top_class

        return SemanticLabel(
            bucket=bucket,
            dominant=dominant,
            mixed=mixed,
            top_class=top_bin,
            second_class=second_bin,
            final_scores=final_scores,
            detailed_scores=detailed_scores,
            majority_threshold=self.spec.mostly_threshold,
            second_threshold=self.spec.hybrid_second_threshold,
            bucket_mode=self.spec.bucket_mode,
        )

    def _bucket_name(self, 
                     top_bin: BinScore, 
                     second_bin: BinScore, 
                     mixed: bool) -> str:
        ...

    def _hybrid_bucket_name(
        self,
        *,
        top_bin: BinScore,
        second_bin: BinScore,
        mixed: bool,
    ) -> str:
        if not mixed:
            return f"{top_bin.name}"

        if self.spec.bucket_mode == "mostly":
            return "review"

        if (
            self.spec.bucket_mode == "hybrid"
            and second_bin.score >= self.spec.hybrid_second_threshold
        ):
            return f"{top_bin.name}_{second_bin.name}"

        return "review"


class SemanticLabeler:
    """Adapter from classifier to your Labeler shape."""

    def __init__(self, classifier: SemanticClassifier) -> None:
        self.classifier = classifier

    def label(self, tile: Tile) -> SemanticLabel:
        if tile.read is None:
            raise ValueError("cannot classify tile with tile.read is None")
        return self.classifier.classify_tile(tile.read.array)


