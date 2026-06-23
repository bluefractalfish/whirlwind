
from dataclasses import dataclass, field
from typing import Any



@dataclass(frozen=True)
class DamageReviewLabel:
    bucket: str
    dominant: str

    # Final training label: true if damaged.
    # Keep None for review candidates.
    damage_label: bool | None

    # Routing/review score only.
    damage_likelihood: float
    route_source: str

    review_required: bool
    review_reason: str

    inside_damage_area: bool = False
    intersects_damage_area: bool = False
    distance_to_damage_line: float | None = None

    semantic_top_class: str | None = None
    semantic_confidence: str | None = None
    semantic_top_score: float | None = None
    semantic_second_class: str | None = None
    semantic_margin: float | None = None

    extra: dict[str, Any] = field(default_factory=dict)

    def metadata(self) -> dict[str, Any]:
        return {
            "damage": {
                "bucket": self.bucket,
                "dominant": self.dominant,
                "damage_label": self.damage_label,
                "damage_likelihood": self.damage_likelihood,
                "route_source": self.route_source,
                "review_required": self.review_required,
                "review_reason": self.review_reason,
                "inside_damage_area": self.inside_damage_area,
                "intersects_damage_area": self.intersects_damage_area,
                "distance_to_damage_line": self.distance_to_damage_line,
                "semantic_top_class": self.semantic_top_class,
                "semantic_confidence": self.semantic_confidence,
                "semantic_top_score": self.semantic_top_score,
                "semantic_second_class": self.semantic_second_class,
                "semantic_margin": self.semantic_margin,
                **self.extra,
            }
        } 

