

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import open_clip
import torch
from huggingface_hub import hf_hub_download
from PIL import Image

from whirlwind.adapters.display.colorcontrols import tile_to_rgb_uint8
from whirlwind.adapters.label.semantic_labels import BinScore, SemanticLabel
from whirlwind.bridges.specs.semclass import SCSpec
from whirlwind.domain.tile import Tile
from whirlwind.prompts.detailed_classes import (
    DETAILED_CLASSES,
    DETAILED_TO_FINAL,
    FINAL_CLASSES,
    FINAL_TO_DETAILED_CLASSES,
    PROMPTS_BY_DETAILED_CLASS,
    REVIEW_CLASS,
)
from whirlwind.prompts.tile_classes import (
        DETAIL_AGREEMENT_MIN_MARGIN, 
        DETAIL_AGREEMENT_MIN_SCORE, 
        FINAL_CLASS_PROMPTS, 
        FINAL_CLASS_RULES, 
        TIE_BREAK_ORDER, 
        FinalClassRule
    )


LOGGER = logging.getLogger(__name__)

PROMPT_TOP_K = 2


@dataclass(frozen=True)
class PromptBank:
    class_order: tuple[str, ...]
    prompts_by_class: dict[str, tuple[str, ...]]
    texts: tuple[str, ...]
    text_to_class: tuple[str, ...]
    prompt_indices_by_class: dict[str, tuple[int, ...]]


@dataclass(frozen=True)
class DecisionSummary:
    accepted: bool
    bucket: str
    dominant: str
    mixed: bool
    reasons: tuple[str, ...]
    coarse_ranked: tuple[tuple[str, float], ...]
    detail_ranked: tuple[tuple[str, float], ...]


def stable_rank(
    scores: Mapping[str, float],
    class_order: Sequence[str],
) -> list[tuple[str, float]]:
    order_index = {name: idx for idx, name in enumerate(class_order)}
    return sorted(
        ((name, float(score)) for name, score in scores.items()),
        key=lambda kv: (-kv[1], order_index.get(kv[0], 10**9), kv[0]),
    )


def aggregate_prompt_logits(
    prompt_logits: torch.Tensor,
    prompt_indices_by_class: Mapping[str, Sequence[int]],
    class_order: Sequence[str],
    *,
    top_k: int = PROMPT_TOP_K,
) -> torch.Tensor:
    class_logits: list[torch.Tensor] = []

    for class_name in class_order:
        idxs = tuple(prompt_indices_by_class[class_name])
        if not idxs:
            raise ValueError(f"class '{class_name}' has no prompt indices")
        values = prompt_logits[list(idxs)]
        k = min(max(int(top_k), 1), int(values.numel()))
        class_logits.append(torch.topk(values, k=k).values.mean())

    return torch.stack(class_logits)

    def _score_bank(
        self,
        image_features: torch.Tensor,
        bank: PromptBank,
        text_features: torch.Tensor,
    ) -> dict[str, float]: 

        prompt_logits = (100.0 * image_features @ text_features.T).squeeze(0)
        class_logits = aggregate_prompt_logits(
            prompt_logits,
            bank.prompt_indices_by_class,
            bank.class_order,
            top_k=PROMPT_TOP_K,
        )
        return softmax_scores(class_logits, bank.class_order)

def softmax_scores(
    class_logits: torch.Tensor,
    class_order: Sequence[str],
) -> dict[str, float]:
    probs = class_logits.softmax(dim=0).detach().cpu().numpy()
    return {
        class_name: float(prob)
        for class_name, prob in zip(class_order, probs, strict=False)
    }




def decide_final_class(
    coarse_scores: Mapping[str, float],
    detail_final_scores: Mapping[str, float],
    *,
    class_rules: Mapping[str, FinalClassRule],
) -> DecisionSummary:
    coarse_ranked = tuple(stable_rank(coarse_scores, TIE_BREAK_ORDER))
    detail_ranked = tuple(stable_rank(detail_final_scores, TIE_BREAK_ORDER))

    top_class, top_score = coarse_ranked[0]
    second_class, second_score = (
        coarse_ranked[1] if len(coarse_ranked) > 1 else ("none", 0.0)
    )

    detail_top_class, detail_top_score = detail_ranked[0]
    _, detail_second_score = (
        detail_ranked[1] if len(detail_ranked) > 1 else ("none", 0.0)
    )

    review_score = float(coarse_scores.get(REVIEW_CLASS, 0.0))
    reasons: list[str] = []

    if top_class == REVIEW_CLASS:
        reasons.append("coarse_top_is_review")
    else:
        rule = class_rules[top_class]
        if top_score < rule.min_score:
            reasons.append(f"top_score_below_min:{top_score:.4f}<{rule.min_score:.4f}")
        if (top_score - second_score) < rule.min_margin:
            reasons.append(
                f"margin_below_min:{(top_score-second_score):.4f}<{rule.min_margin:.4f}"
            )
        if second_score > rule.max_second_score:
            reasons.append(
                f"runner_up_too_high:{second_score:.4f}>{rule.max_second_score:.4f}"
            )
        if review_score > rule.max_review_score:
            reasons.append(
                f"review_score_too_high:{review_score:.4f}>{rule.max_review_score:.4f}"
            )
        if detail_top_class != top_class:
            reasons.append(
                f"coarse_detail_disagreement:{top_class}!={detail_top_class}"
            )
        if detail_top_score < DETAIL_AGREEMENT_MIN_SCORE:
            reasons.append(
                "detail_top_score_below_min:"
                f"{detail_top_score:.4f}<{DETAIL_AGREEMENT_MIN_SCORE:.4f}"
            )
        if (detail_top_score - detail_second_score) < DETAIL_AGREEMENT_MIN_MARGIN:
            reasons.append(
                "detail_margin_below_min:"
                f"{(detail_top_score-detail_second_score):.4f}"
                f"<{DETAIL_AGREEMENT_MIN_MARGIN:.4f}"
            )

    accepted = not reasons
    bucket = top_class if accepted else REVIEW_CLASS
    dominant = top_class if accepted else REVIEW_CLASS

    return DecisionSummary(
        accepted=accepted,
        bucket=bucket,
        dominant=dominant,
        mixed=not accepted,
        reasons=tuple(reasons),
        coarse_ranked=coarse_ranked,
        detail_ranked=detail_ranked,
    )


def label_from_decision(
    decision: DecisionSummary,
    *,
    final_scores: Mapping[str, float],
    detailed_scores: Mapping[str, float],
    spec: SCSpec,
) -> SemanticLabel:
    top_class, top_score = decision.coarse_ranked[0]
    second_class, second_score = (
        decision.coarse_ranked[1] if len(decision.coarse_ranked) > 1 else ("none", 0.0)
    )

    return SemanticLabel(
        bucket=decision.bucket,
        dominant=decision.dominant,
        mixed=decision.mixed,
        top_class=BinScore(name=top_class, score=float(top_score)),
        second_class=BinScore(name=second_class, score=float(second_score)),
        final_scores={k: float(v) for k, v in final_scores.items()},
        detailed_scores={k: float(v) for k, v in detailed_scores.items()},
        majority_threshold=spec.mostly_threshold,
        second_threshold=spec.hybrid_second_threshold,
        bucket_mode=spec.bucket_mode,
    )


class SemanticClassifier:

    def __init__(
        self,
        spec: SCSpec,
        *,
        final_class_rules: Mapping[str, FinalClassRule] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:

        self.spec = spec
        self.device = torch.device(spec.device)
        self.logger = logger or LOGGER

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

        self.final_bank = build_prompt_bank(FINAL_CLASSES, FINAL_CLASS_PROMPTS)
        self.detailed_bank = build_prompt_bank(DETAILED_CLASSES, PROMPTS_BY_DETAILED_CLASS)

        self.final_text_features = self._encode_text_bank(self.final_bank)
        self.detailed_text_features = self._encode_text_bank(self.detailed_bank)

        merged_rules = dict(FINAL_CLASS_RULES)
        if final_class_rules is not None:
            merged_rules.update(final_class_rules)
        self.final_class_rules = merged_rules

    def _resolve_checkpoint(self, spec: SCSpec) -> str:
        if spec.checkpoint_path is not None:
            return str(Path(spec.checkpoint_path).expanduser())

        return hf_hub_download(
            repo_id=spec.hf_repo,
            filename=f"RemoteCLIP-{spec.model_name}.pt",
            cache_dir=str(Path(spec.cache_dir).expanduser()),
        )

    def _encode_text_bank(self, bank: PromptBank) -> torch.Tensor:
        with torch.no_grad():
            text_tokens = self.tokenizer(list(bank.texts)).to(self.device)
            text_features = self.model.encode_text(text_tokens)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
        return text_features

    def _encode_image(self, image: Image.Image) -> torch.Tensor:
        image_tensor = self.preprocess(image).unsqueeze(0).to(self.device)
        with torch.no_grad():
            image_features = self.model.encode_image(image_tensor)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        return image_features

    def _score_bank(
        self,
        image_features: torch.Tensor,
        bank: PromptBank,
        text_features: torch.Tensor,
    ) -> dict[str, float]:
        prompt_logits = (100.0 * image_features @ text_features.T).squeeze(0)
        class_logits = aggregate_prompt_logits(
            prompt_logits,
            bank.prompt_indices_by_class,
            bank.class_order,
            top_k=PROMPT_TOP_K,
        )
        return softmax_scores(class_logits, bank.class_order)

    def classify_tile(
        self,
        tile: np.ndarray,
        *,
        tile_id: str | None = None,
    ) -> SemanticLabel:
        rgb = tile_to_rgb_uint8(
            tile,
            layout=self.spec.layout,
            rgb_bands=self.spec.rgb_bands,
            p_low=self.spec.percentile_low,
            p_high=self.spec.percentile_high,
        )
        image = Image.fromarray(rgb).convert("RGB")
        image_features = self._encode_image(image)

        coarse_scores = self._score_bank(
            image_features=image_features,
            bank=self.final_bank,
            text_features=self.final_text_features,
        )
        detailed_scores = self._score_bank(
            image_features=image_features,
            bank=self.detailed_bank,
            text_features=self.detailed_text_features,
        )
        detail_final_scores = collapse_detailed_to_final(detailed_scores)

        decision = decide_final_class(
            coarse_scores,
            detail_final_scores,
            class_rules=self.final_class_rules,
        )
        label = label_from_decision(
            decision,
            final_scores=coarse_scores,
            detailed_scores=detailed_scores,
            spec=self.spec,
        )

        self._log_decision(
            tile_id=tile_id,
            label=label,
            decision=decision,
            coarse_scores=coarse_scores,
            detail_final_scores=detail_final_scores,
            detailed_scores=detailed_scores,
        )
        return label

    def classify_tiles(
        self,
        tiles: Sequence[np.ndarray],
        *,
        tile_ids: Sequence[str | None] | None = None,
    ) -> list[SemanticLabel]:
        if tile_ids is None:
            tile_ids = [None] * len(tiles)
        return [
            self.classify_tile(tile, tile_id=tile_id)
            for tile, tile_id in zip(tiles, tile_ids, strict=False)
        ]

    def _log_decision(
        self,
        *,
        tile_id: str | None,
        label: SemanticLabel,
        decision: DecisionSummary,
        coarse_scores: Mapping[str, float],
        detail_final_scores: Mapping[str, float],
        detailed_scores: Mapping[str, float],
    ) -> None:
        detailed_ranked = stable_rank(detailed_scores, DETAILED_CLASSES)
        top_detail_name, top_detail_score = detailed_ranked[0]

        winning_family = (
            label.dominant if label.dominant in FINAL_TO_DETAILED_CLASSES else REVIEW_CLASS
        )
        family_detail_scores = {
            name: float(score)
            for name, score in detailed_scores.items()
            if DETAILED_TO_FINAL.get(name, REVIEW_CLASS) == winning_family
        }

        payload = {
            "tile_id": tile_id,
            "bucket": label.bucket,
            "dominant": label.dominant,
            "mixed": label.mixed,
            "reasons": list(decision.reasons),
            "coarse_ranked": [
                {"name": name, "score": round(score, 6)}
                for name, score in decision.coarse_ranked
            ],
            "detail_family_ranked": [
                {"name": name, "score": round(score, 6)}
                for name, score in decision.detail_ranked
            ],
            "top_detailed_class": {
                "name": top_detail_name,
                "score": round(top_detail_score, 6),
            },
            "coarse_scores": {k: round(float(v), 6) for k, v in coarse_scores.items()},
            "detail_family_scores": {
                k: round(float(v), 6) for k, v in detail_final_scores.items()
            },
            "winning_family_detailed_scores": {
                k: round(float(v), 6) for k, v in family_detail_scores.items()
            },
        }
        self.logger.info("semantic_classifier %s", json.dumps(payload, sort_keys=True))


class SemanticLabeler:
    """Adapter from classifier to the existing Labeler shape."""

    def __init__(self, classifier: SemanticClassifier) -> None:
        self.classifier = classifier

    def label(self, tile: Tile) -> SemanticLabel:
        if tile.read is None:
            raise ValueError("cannot classify tile with tile.read is None")
        return self.classifier.classify_tile(
            tile.read.array,
            tile_id=tile.tile_id,
        )
