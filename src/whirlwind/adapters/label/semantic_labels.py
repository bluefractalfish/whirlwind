from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Sequence

from whirlwind.prompts.tile_classes import (

        TARGET_CLASSES, 
        MIN_TOP_SCORE, 
        LOW_EVIDENCE, 
        TIE_MARGIN, 
        MEDIUM_CONFIDENCE_MIN_MARGIN, 
        DETAIL_AGREEMENT_MIN_SCORE, 
        DETAIL_AGREEMENT_MIN_MARGIN, 
        DETAIL_AGREEMENT_MIN_SCORE, 
        REVIEW_CLASS, 
        TIE_BREAK_ORDER, 
        ClassThreshold 
    )


Confidence = Literal["high","medium", "low","review"]



@dataclass(frozen=True)
class SemanticLabel:

    bucket: str
    dominant: str 

    # assigned to a real class if true
    accepted: bool


    confidence: Confidence 
    confidence_score: float 

    top_class: str
    second_class: str
    margin: float

    top_detailed_class: str
    second_detailed_class: str
    detail_margin: float
    detail_agrees: bool 

    review_reasons: tuple[str, ...] = field(default_factory=tuple)

    final_scores: dict[str, float] = field(default_factory=dict)
    detailed_scores: dict[str, float] = field(default_factory=dict)

    def metadata(self) -> dict[str, Any]:
        return {
            "semantic": {
                "bucket": self.bucket,
                "dominant": self.dominant,
                "accepted": self.accepted,
                "confidence": self.confidence, 
                "confidence_score": self.confidence_score, 

                "review_reasons": list(self.review_reasons),

                "top_class": self.top_class,
                "second_class": self.second_class,
                "margin": self.margin,
                
                "top_detailed_class": self.top_detailed_class,
                "second_detailed_class": self.second_detailed_class,
                "detail_margin": self.detail_margin,
                "detail_agrees": self.detail_agrees, 

                "final_scores": self.final_scores,
                "detailed_scores": self.detailed_scores,
            }
        } 

    @classmethod
    def from_decision(cls, 
                      decision: "DecisionSummary",
                      class_scores: Mapping[str, float],
                      detailed_scores: Mapping[str, float]
                        ) -> "SemanticLabel":

       top_class, top_score = decision.coarse_ranked[0]
       sec_class, sec_score = (
               decision.coarse_ranked[1] 
               if len(decision.coarse_ranked) > 1 
               else ("none",0.0)

            ) 

       top_detail, top_detail_score = decision.detail_ranked[0] 
       sec_detail, sec_detail_score = (
               decision.detail_ranked[1] 
               if len(decision.detail_ranked) > 1 
               else ("none",0.0)

            )

       return cls(
                bucket = decision.bucket, 
                dominant=decision.dominant,
                accepted=decision.accepted,
                
                confidence=decision.confidence, 
                confidence_score=decision.confidence_score,

                top_class=top_class, 
                second_class=sec_class, 
                margin=(top_score-sec_score),
                top_detailed_class=top_detail, 
                second_detailed_class=sec_detail,
                detail_margin=(top_detail_score - sec_detail_score), 
                detail_agrees=decision.detail_agrees, 

                review_reasons=decision.reasons, 
                final_scores={k: float(v) for k, v in class_scores.items()}, 
                detailed_scores={k: float(v) for k,v in detailed_scores.items()} 
                )



@dataclass(frozen=True)
class DecisionSummary:
    accepted: bool
    bucket: str
    dominant: str

    confidence: Confidence 
    confidence_score: float 
    
    reasons: tuple[str, ...]
    coarse_ranked: tuple[tuple[str, float], ...]
    detail_ranked: tuple[tuple[str, float], ...] 

    detail_agrees: bool 


    @classmethod 
    def build_from(cls, 
               coarse_scores: Mapping[str, float],
               detailed_scores: Mapping[str, float],
               *, 
               class_thresholds: Mapping[str, ClassThreshold],
               ) -> "DecisionSummary":
        
        # rank real classes. review is not a class, but a fallback 
        real_scores = { 
            name: float(score)
            for name, score in coarse_scores.items()
            if name in TARGET_CLASSES
            }

        if not real_scores: 
            return cls(
                    accepted=False, 
                    bucket=REVIEW_CLASS, 
                    dominant=REVIEW_CLASS, 
                    confidence="review",
                    confidence_score=0.0, 
                    reasons=("no_real_class: no evidence",), 
                    coarse_ranked=((REVIEW_CLASS, 0.0),),
                    detail_ranked=((REVIEW_CLASS, 0.0),),
                    detail_agrees=False
                    ) 
        coarse_ranked = tuple(stable_rank(real_scores, TIE_BREAK_ORDER))
        detailed_ranked = tuple(stable_rank(detailed_scores, TIE_BREAK_ORDER))
        
        top_class, top_score = coarse_ranked[0] 
        second_class, second_score = (
                coarse_ranked[1] if len(coarse_ranked) > 1 else ("none",0.0)
        )


        margin = float(top_score - second_score)

        top_detail, top_detail_score = detailed_ranked[0]
        second_detail, second_detail_score = (
                detailed_ranked[1] if len(detailed_ranked) > 1 else ("none", 0.0)
            )

        detail_margin = float(top_detail_score - second_detail_score)
        detail_agrees = top_detail == top_class  

        reasons: list[str] = []

        # edge case 1: almost zero real class evidence 
        if top_score < MIN_TOP_SCORE: 
            reasons.append(
                f"true_edge_low_evidence:{top_score:.4f}<{MIN_TOP_SCORE:.4f}"
            )

        # edge case 2: weak score and nearly tied.
        elif top_score < LOW_EVIDENCE and margin < TIE_MARGIN:
            reasons.append(
                "true_edge_weak_tie:"
                f"score={top_score:.4f}<"
                f"{LOW_EVIDENCE:.4f},"
                f"margin={margin:.4f}<"
                f"{TIE_MARGIN:.4f}"
            )

        if reasons:
            return cls(
                accepted=False,
                bucket=REVIEW_CLASS,
                dominant=top_class,
                confidence="review",
                confidence_score=float(top_score),
                reasons=tuple(reasons),
                coarse_ranked=coarse_ranked,
                detail_ranked=detailed_ranked,
                detail_agrees=detail_agrees,
            )
        
        # if no edge cases, assign real class 

        th = class_thresholds[top_class] 

        confidence = th.confidence(top_score, 
                      margin, 
                      second_score, 
                      top_detail_score, 
                      detail_margin, 
                      detail_agrees)  

        confidence_score = float((top_score + max(margin, 0.0)) / 2.0)
        
        return cls(
                accepted=True, 
                bucket=top_class, 
                dominant=top_class, 
                confidence=confidence, 
                confidence_score=confidence_score, 
                reasons=("real_class_assigned",),
                coarse_ranked=coarse_ranked, 
                detail_ranked=detailed_ranked, 
                detail_agrees=detail_agrees
                )

def stable_rank(
    scores: Mapping[str, float],
    class_order: Sequence[str],
) -> list[tuple[str, float]]:
    """assign real_class unless unclassifiable"""
    order_index = {name: idx for idx, name in enumerate(class_order)}
    return sorted(
        ((name, float(score)) for name, score in scores.items()),
        key=lambda kv: (-kv[1], order_index.get(kv[0], 10**9), kv[0]),
    )




