import torch
from dataclasses import dataclass, asdict 
from typing import Mapping, Sequence
from whirlwind.adapters.label.semantic_labels import SemanticLabel
from whirlwind.bridges.specs.semclass import SCSpec
from whirlwind.prompts.detailed_classes import DETAILED_TO_FINAL, FINAL_CLASSES, REVIEW_CLASS
from whirlwind.prompts.tile_classes import CLASS_THRESHOLDS, DETAIL_AGREEMENT_MIN_MARGIN, DETAIL_AGREEMENT_MIN_SCORE, TIE_BREAK_ORDER, ClassThreshold

@dataclass
class PromptBank: 
    classes: tuple[str,...]
    prompts_by_class: dict[str, tuple[str, ...]]
    text_sets: tuple[str, ...]
    text_to_class: tuple[str, ...]
    prompt_indices_by_class: dict[str, tuple[int, ...]]

    @classmethod
    def build(cls, classes, prompts_by_class) -> "PromptBank":
        text_sets: list[str] = []
        text_to_class: list[str] = [] 

        prompts_copy: dict[str, tuple[str, ...]] = {}

        for class_name in classes: 
            prompts = tuple(prompts_by_class[class_name]) 
            if not prompts: 
                raise ValueError(f"class `{class_name} has no prompts")
            prompts_copy[class_name] = prompts 
            for prompt in prompts: 
                text_sets.append(prompt) 
                text_to_class.append(class_name) 

        prompt_indices_by_class: dict[str, tuple[int,...]] = {
                class_name: tuple(
                    i for i, mapped in enumerate(text_to_class) if mapped == class_name
                    )
                for class_name in classes
            }
        return cls(classes=tuple(classes), 
                   prompts_by_class=prompts_copy, 
                   text_sets=tuple(text_sets), 
                   text_to_class=tuple(text_to_class), 
                   prompt_indices_by_class=prompt_indices_by_class
                )
    
    def record(self) -> dict[str, str]: 
        return asdict(self)


def collapse(
    detailed_scores: Mapping[str, float],
    *,
    final_classes: Sequence[str] = FINAL_CLASSES,
    detailed_to_final: Mapping[str, str] = DETAILED_TO_FINAL,
) -> dict[str, float]:

    grouped: dict[str, list[float]] = {name: [] for name in final_classes}

    for detailed_name, score in detailed_scores.items():
        class_name = detailed_to_final.get(detailed_name, REVIEW_CLASS)
        grouped.setdefault(class_name, []).append(float(score))

    collapsed = {
        class_name: (max(scores) if scores else 0.0)
        for class_name, scores in grouped.items()
    }

    total = float(sum(collapsed.values()))
    if total <= 0.0:
        return {name: 0.0 for name in final_classes}

    return {name: float(value / total) for name, value in collapsed.items()}




