
import logging
from typing import Mapping, Sequence, Any

import numpy as np
import torch
from PIL import Image

from whirlwind.adapters.display.colorcontrols import tile_to_rgb_uint8
from whirlwind.adapters.label.labels.semantic_labels import SemanticLabel, DecisionSummary
from whirlwind.neural.semantic_embedder import SemanticIntellect
from whirlwind.bridges.specs.semclass import SCSpec
from whirlwind.domain.tile import Tile
from whirlwind.prompts.prompt_builders import PromptBank, collapse
from whirlwind.models.helpers.logit import PromptLogitator
from whirlwind.prompts.detailed_classes import (
    DETAILED_CLASSES,
    PROMPTS_BY_DETAILED_CLASS,
)
from whirlwind.prompts.tile_classes import (
        TARGET_CLASSES, 
        FINAL_CLASS_PROMPTS, 
        CLASS_THRESHOLDS, 
        ClassThreshold
    )



LOGGER = logging.getLogger(__name__)
TOP_K_CLASSES = 2

class SemanticLabelTriage:
    """Adapter from classifier to the existing Labeler shape."""

    def __init__(self, classifier: "SemanticClassTriage") -> None:
        self.classifier = classifier

    def label(self, tile: "Tile") -> "SemanticLabel":
        if tile.read is None:
            raise ValueError("cannot classify tile with tile.read is None")
        return self.classifier.classify(
            tile.read.array,
            tile_id=tile.tile_id,
        ) 

    def metadata(self, tile: "Tile") -> dict[str, Any]:  
        semantic_label = self.label(tile)

        payload = semantic_label.metadata()
        semantic = payload.get("semantic", {})

        return {
            "bucket": semantic.get("bucket"),
            "dominant": semantic.get("dominant"),
            "accepted": semantic.get("accepted"),
            "confidence": semantic.get("confidence"),
            "confidence_score": semantic.get("confidence_score"),
            "top_class": semantic.get("top_class"),
            "top_score": semantic.get("top_score"),
            "second_class": semantic.get("second_class"),
            "second_score": semantic.get("second_score"),
            "margin": semantic.get("margin"),
            "top_detailed_class": semantic.get("top_detailed_class"),
            "top_detailed_score": semantic.get("top_detailed_score"),
            "second_detailed_class": semantic.get("second_detailed_class"),
            "detail_margin": semantic.get("detail_margin"),
            "detail_agrees": semantic.get("detail_agrees"),
            "review_reasons": semantic.get("review_reasons", []),
            "final_scores": semantic.get("final_scores", {}),
            "detailed_scores": semantic.get("detailed_scores", {}),
        }

class SemanticClassTriage: 
    def __init__(
            self, 
            spec: SCSpec, 
            *, 
            class_thresholds: Mapping[str, ClassThreshold] | None = None, 
            logger: logging.Logger | None=None
            ) -> None: 


        self.spec = spec 
        self.logger = logger or LOGGER 

        self.class_bank = PromptBank.build(
                classes=TARGET_CLASSES, 
                prompts_by_class=FINAL_CLASS_PROMPTS) 

        self.detailed_class_bank = PromptBank.build(
                classes=DETAILED_CLASSES, 
                prompts_by_class=PROMPTS_BY_DETAILED_CLASS) 

        
        self.class_thresholds = self._merge(class_thresholds) 
        
        self.intellect = SemanticIntellect(self.spec)

        self.class_text_features = self.intellect.encode_text_features(
                self.class_bank
                ) 
        self.detailed_text_features = self.intellect.encode_text_features(
                self.detailed_class_bank
                )

    def _merge(self, class_thresholds) -> dict[Any,Any]:
        merged_thresholds = dict(CLASS_THRESHOLDS) 
        if class_thresholds is not None: 
            merged_thresholds.update(class_thresholds) 
        return merged_thresholds

    def _logits(self,
                image_features: torch.Tensor,
                text_features: torch.Tensor) -> torch.Tensor:  
        return (100.0 * image_features @ text_features.T).squeeze(0)

    def _softmax_logits(self, 
                    image_features: torch.Tensor, 
                    bank: PromptBank, 
                    text_features: torch.Tensor, 
                    ) -> dict[str, float]:  
        
        logitator = PromptLogitator(
                i_features=image_features, 
                t_features=text_features, 
                logit_scale=self.spec.logit_scale, 
                bank=bank
                ) 

        return logitator.resolve_scores(TOP_K_CLASSES, "softmax")

    def classify(self, 
                 tile: np.ndarray, 
                 *, 
                 tile_id: str | None=None, 
                 ) -> SemanticLabel:  

        rgb = tile_to_rgb_uint8(
                tile, 
                layout = self.spec.layout, 
                rgb_bands=self.spec.rgb_bands, 
                p_low = self.spec.percentile_low, 
                p_high = self.spec.percentile_high, 
            ) 

        image = Image.fromarray(rgb).convert("RGB")
        image_features = self.intellect.encode_image_features(image)

        coarse_scores = self._softmax_logits(
                image_features=image_features, 
                bank = self.class_bank, 
                text_features= self.class_text_features,
                )  

        detailed_scores = self._softmax_logits(
                image_features=image_features, 
                bank = self.detailed_class_bank, 
                text_features = self.detailed_text_features, 
                )

        detail_final_scores = collapse(detailed_scores)
        
        decision = DecisionSummary.build_from(
                                        coarse_scores=coarse_scores,
                                        detailed_scores=detail_final_scores, 
                                        class_thresholds=self.class_thresholds)

        label =  SemanticLabel.from_decision(decision=decision, 
                                          class_scores=coarse_scores,
                                          detailed_scores=detailed_scores) 

        self._log_decision(tile_id=tile_id, label=label)
        return label 

    def _log_decision(self, tile_id: str | None, label: SemanticLabel) -> None:
        if not self.spec.log_decisions:
            return

        self.logger.debug(
            "triage decision",
            extra={ 
            "tile_id": tile_id,
            "bucket": label.bucket,
            "dominant": label.dominant,
            "accepted": label.accepted,
            "confidence": label.confidence,
            "confidence_score": label.confidence_score,
            "top_class": label.top_class,
            "second_class": label.second_class,
            "margin": label.margin,
            "detail_agrees": label.detail_agrees,
            "top_detailed_class": label.top_detailed_class,
            "review_reasons": label.review_reasons,
            },
        )

