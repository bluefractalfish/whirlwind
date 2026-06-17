
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence, Any

import numpy as np
import open_clip
import torch
from huggingface_hub import hf_hub_download
from PIL import Image

from whirlwind.adapters.display.colorcontrols import tile_to_rgb_uint8
from whirlwind.adapters.label.semantic_labels import SemanticLabel, DecisionSummary
from whirlwind.bridges.specs.semclass import SCSpec
from whirlwind.domain.tile import Tile
from whirlwind.prompts.prompt_builders import PromptBank, collapse
from whirlwind.models.helpers.logit import PromptLogitator
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
        CLASS_THRESHOLDS, 
        TIE_BREAK_ORDER, 
        ClassThreshold
    )



LOGGER = logging.getLogger(__name__)
TOP_K_CLASSES = 2


class SemanticClassifier: 
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
                classes=FINAL_CLASSES, 
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
        
        decision = DecisionSummary.build(
                                        coarse_scores=coarse_scores,
                                        detail_final_scores=detail_final_scores, 
                                        class_thresholds=self.class_thresholds)

        label =  SemanticLabel.from_decision(decision=decision, 
                                          class_scores=coarse_scores,
                                          detailed_scores=detailed_scores) 

        self._log_decision(tile_id=tile_id, label=label)
        return label 

    def bulk_classify(self, 
                      tiles: Sequence[np.ndarray],
                      *, 
                      tile_ids: Sequence[str | None] | None = None, 
                      ) -> list[SemanticLabel]:
        ... 
    def record_decision(self, 
                        *, 
                        tile_id: str | None, 
                        label: SemanticLabel, 
                        coarse_scores: Mapping[str, float], 
                        detail_scores: Mapping[str, float], 
                        detail_class_scores: Mapping[str, float]
                        ) -> None: 
        ... 
    def _log_decision(self, tile_id: str | None, label: SemanticLabel) -> None:
        if not self.spec.log_decisions:
            return

        self.logger.debug(
            "semantic decision",
            extra={
                "tile_id": tile_id,
                "bucket": label.bucket,
                "candidate": label.candidate,
                "accepted": label.accepted,
                "top_class": label.top_class.name,
                "top_score": label.top_class.score,
                "second_class": label.second_class.name, 
                "second_score": label.second_class.score, 
                "margin": label.margin,
                "review_score": label.review_score,
                "detail_top_class": label.top_detailed_class.name,
                "detail_top_score": label.top_detailed_class.score,
                "review_reasons": label.review_reasons,
            },
        )



class SemanticLabeler:
    """Adapter from classifier to the existing Labeler shape."""

    def __init__(self, classifier: SemanticClassifier) -> None:
        self.classifier = classifier

    def label(self, tile: Tile) -> SemanticLabel:
        if tile.read is None:
            raise ValueError("cannot classify tile with tile.read is None")
        return self.classifier.classify(
            tile.read.array,
            tile_id=tile.tile_id,
        )


class SemanticIntellect: 

    def __init__(self, spec: SCSpec) -> None:

        self.device = torch.device(spec.device)
        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
              spec.model_name
            ) 
        self.tokenizer = open_clip.get_tokenizer(spec.model_name)
        if spec.checkpoint_path is not None:
            checkpoint_path = str(Path(spec.checkpoint_path).expanduser())
        else:
            checkpoint_path = hf_hub_download(
                      repo_id=spec.hf_repo, 
                      filename=f"RemoteCLIP-{spec.model_name}.pt",
                      cache_dir=str(Path(spec.cache_dir).expanduser())
                    )
        checkpoint = torch.load(checkpoint_path, map_location="cpu")
        if isinstance(checkpoint, dict) and "state_dict" in checkpoint: 
              checkpoint = checkpoint["state_dict"]
        self.model.load_state_dict(checkpoint, strict=False) 
        self.model = self.model.to(self.device).eval()
    
    def encode_text_features(self, 
               bank: PromptBank
               ) -> torch.Tensor: 
        with torch.no_grad(): 
            text_tokens = self.tokenizer(list(bank.text_sets)).to(self.device)
            text_features = self.model.encode_text(text_tokens)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
        return text_features
    
    def encode_image_features(self, image: Image.Image) -> torch.Tensor: 
        image_tensor = self.preprocess(image).unsqueeze(0).to(self.device) 
        with torch.no_grad(): 
            image_features = self.model.encode_image(image_tensor) 
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        return image_features
