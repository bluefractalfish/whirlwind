from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Sequence

from whirlwind.prompts.tile_classes import DETAIL_AGREEMENT_MIN_MARGIN, DETAIL_AGREEMENT_MIN_SCORE, REVIEW_CLASS, TIE_BREAK_ORDER, ClassThreshold 



@dataclass 
class BinScore: 
    name: str 
    score: float 



@dataclass(frozen=True)
class SemanticLabel:

    bucket: str
    dominant: str
    accepted: bool

    top_class: str
    second_class: str
    margin: float
    review_score: float

    top_detailed_class: str
    second_detailed_class: str
    detail_margin: float

    review_reasons: tuple[str, ...] = field(default_factory=tuple)

    final_scores: dict[str, float] = field(default_factory=dict)
    detailed_scores: dict[str, float] = field(default_factory=dict)

    def metadata(self) -> dict[str, Any]:
        return {
            "semantic": {
                "bucket": self.bucket,
                "dominant": self.dominant,
                "accepted": self.accepted,
                "review_reasons": list(self.review_reasons),

                "top_class": self.top_class,
                "second_class": self.second_class,
                "margin": self.margin,
                "review_score": self.review_score,
                
                "top_detailed_class": self.top_detailed_class,
                "second_detailed_class": self.second_detailed_class,
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
       top_class, top_score = decision.coarse_ranked[0]
       sec_class, sec_score = (
               decision.coarse_ranked[1] if len(decision.coarse_ranked) > 1 else ("none",0.0)
               ) 

       top_detail, top_detail_score = decision.detail_ranked[0] 
       sec_detail, sec_detail_score = (
               decision.detail_ranked[1] if len(decision.detail_ranked) > 1 else ("none",0.0)
               )

       return SemanticLabel(
                bucket = decision.bucket, 
                dominant=decision.dominant,
                accepted=decision.accepted,
                top_class=top_class, 
                second_class=sec_class, 
                margin=(top_score-sec_score),
                review_score=decision.review_score,
                top_detailed_class=top_detail, 
                second_detailed_class=sec_detail, 
                detail_margin=(top_detail_score - sec_detail_score), 
                review_reasons=decision.reasons, 
                final_scores={k: float(v) for k, v in class_scores.items()}, 
                detailed_scores={k: float(v) for k,v in detailed_scores.items()} 
                )



@dataclass(frozen=True)
class DecisionSummary:
    accepted: bool
    bucket: str
    dominant: str
    
    reasons: tuple[str, ...]
    coarse_ranked: tuple[tuple[str, float], ...]
    detail_ranked: tuple[tuple[str, float], ...] 
    review_score: float


    @classmethod 
    def build_from(cls, 
               coarse_scores: Mapping[str, float],
               detailed_scores: Mapping[str, float],
               *, 
               class_thresholds: Mapping[str, ClassThreshold],
               ) -> "DecisionSummary":
        
        coarse_ranked = tuple(stable_rank(coarse_scores, TIE_BREAK_ORDER))
        detailed_ranked = tuple(stable_rank(detailed_scores, TIE_BREAK_ORDER))
        
        top_coarse_bin, top_score = coarse_ranked[0] 
        top_detailed_bin, top_detail_score = detailed_ranked[0]
        _, sec_detail_score = (
                detailed_ranked[1] if len(detailed_ranked) > 1 else ("none", 0.0)
            )
        top_class = BinScore(name=top_coarse_bin, score=top_score)
        top_detailed_class = BinScore(name=top_detailed_bin, score=top_detail_score)

        review_score = float(coarse_scores.get(REVIEW_CLASS, 0.0))
        reasons: list[str] = []

        if top_class.name == REVIEW_CLASS:
            reasons.append("top_coarse_score_is_review")
        else:
            th = class_thresholds[top_class.name]
            if top_class.score < th.min_score:
                reasons.append(
                    "top_score_below_min:"
                    f"{top_class.score:.4f}<{th.min_score:.4f}"
                        )
            if review_score > th.max_review_score:
                reasons.append(
                    "review_score_too_high:"
                    f"{review_score:.4f}>{th.max_review_score:.4f}"
                        )
            if top_detailed_class.name != top_class.name:
                reasons.append(
                    "coarse_detail_disagreement:"
                    f"{top_class.name}!={top_detailed_class.name}"
                        ) 
            if top_detailed_class.score < DETAIL_AGREEMENT_MIN_SCORE:
                reasons.append(
                    "top_detailed_score_below_min:"
                    f"{top_detailed_class.score:.4f}<{DETAIL_AGREEMENT_MIN_SCORE:.4f}"
                        )
            if (top_detailed_class.score - sec_detail_score) < DETAIL_AGREEMENT_MIN_MARGIN:
                reasons.append(
                    "detail_margin_below_min:"
                    f"{(top_detailed_class.score - sec_detail_score):.4f}"
                    f"<{DETAIL_AGREEMENT_MIN_MARGIN:.4f}"
                )

        accepted = not reasons 
        bucket = top_class.name if accepted else REVIEW_CLASS 
        dominant = top_detailed_class.name
        
        return DecisionSummary(
                accepted=accepted, 
                bucket=bucket, 
                dominant=dominant, 
                reasons=tuple(reasons),
                coarse_ranked=coarse_ranked, 
                detail_ranked=detailed_ranked, 
                review_score=review_score
            )

def stable_rank(
    scores: Mapping[str, float],
    class_order: Sequence[str],
) -> list[tuple[str, float]]:
    order_index = {name: idx for idx, name in enumerate(class_order)}
    return sorted(
        ((name, float(score)) for name, score in scores.items()),
        key=lambda kv: (-kv[1], order_index.get(kv[0], 10**9), kv[0]),
    )




