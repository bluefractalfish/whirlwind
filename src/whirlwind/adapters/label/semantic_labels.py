import numpy as np
from dataclasses import dataclass, asdict 
from typing import Any, Literal

from whirlwind.bridges.specs.semclass import ArrayLayout 



@dataclass 
class BinScore: 
    name: str 
    score: float 

@dataclass 
class SemanticLabel: 
    """ 
        bucket is used to control shard routing into semantic subdirs

    """

    bucket: str 
    dominant: str 
    mixed: bool 

    top_class: BinScore 
    second_class: BinScore 

    final_scores: dict[str, float]
    detailed_scores: dict[str, float]

    majority_threshold: float 
    second_threshold: float 
    bucket_mode: str 

    def metadata(self) -> dict[str, Any]:
        return asdict(self)


