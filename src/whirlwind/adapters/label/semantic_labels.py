import numpy as np
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Sequence

from whirlwind.bridges.specs.semclass import ArrayLayout, SCSpec
from whirlwind.prompts.tile_classes import DETAIL_AGREEMENT_MIN_MARGIN, DETAIL_AGREEMENT_MIN_SCORE, REVIEW_CLASS, TIE_BREAK_ORDER, ClassThreshold 



@dataclass 
class BinScore: 
    name: str 
    score: float 



@dataclass(frozen=True)
class SemanticLabel:

    bucket: str
    candidate: str
    accepted: bool

    top_class: BinScore 
    second_class: BinScore
    margin: float
    review_score: float

    top_detailed_class: BinScore
    second_detailed_class: BinScore
    detail_margin: float

    review_reasons: tuple[str, ...] = field(default_factory=tuple)

    final_scores: dict[str, float] = field(default_factory=dict)
    detailed_scores: dict[str, float] = field(default_factory=dict)

    def metadata(self) -> dict[str, Any]:
        return {
            "semantic": {
                "bucket": self.bucket,
                "candidate": self.candidate,
                "accepted": self.accepted,
                "review_reasons": list(self.review_reasons),

                "top_class": self.top_class.name,
                "second_class": self.second_class.name,
                "margin": self.margin,
                "review_score": self.review_score,
                
                "top_detailed_class": self.top_detailed_class.name,
                "second_detailed_class": self.second_detailed_class.name,
                "detail_margin": self.detail_margin,

                "final_scores": self.final_scores,
                "detailed_scores": self.detailed_scores,
            }
        } 

    @classmethod
    def from_decision(cls, 
                      decision: DecisionSummary,
                      class_scores: Mapping[str, float],
                      detailed_scores: Mapping[str, float]) -> "SemanticLabel":
        ...

@dataclass(frozen=True)
class DecisionSummary:
    accepted: bool
    bucket: str
    dominant: str
    mixed: bool
    reasons: tuple[str, ...]
    coarse_ranked: tuple[tuple[str, float], ...]
    detail_ranked: tuple[tuple[str, float], ...] 


    @classmethod 
    def build(cls, 
               coarse_scores: Mapping[str, float],
               detail_final_scores: Mapping[str, float],
               *, 
               class_thresholds: Mapping[str, ClassThreshold],
               ) -> "DecisionSummary":
        ...



def stable_rank(
    scores: Mapping[str, float],
    class_order: Sequence[str],
) -> list[tuple[str, float]]:
    order_index = {name: idx for idx, name in enumerate(class_order)}
    return sorted(
        ((name, float(score)) for name, score in scores.items()),
        key=lambda kv: (-kv[1], order_index.get(kv[0], 10**9), kv[0]),
    )



def decide_final_class(
    coarse_scores: Mapping[str, float],
    detail_final_scores: Mapping[str, float],
    *,
    class_rules: Mapping[str, ClassThreshold],
) -> DecisionSummary:
    coarse_ranked = tuple(stable_rank(coarse_scores, TIE_BREAK_ORDER))
    detail_ranked = tuple(stable_rank(detail_final_scores, TIE_BREAK_ORDER))

    top_class, top_score = coarse_ranked[0]

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
    )

