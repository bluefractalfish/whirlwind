from dataclasses import dataclass, field 
from typing import Any


@dataclass 
class SimpleLabel: 
    """
    simplest label object for unary and binary labels
    """

    bucket: str 

    # main class/dir name
    dominant: str 
    
    #optional binary class 
    positive: bool | None=None 

    extra: dict[str, Any] = field(default_factory=dict)

    def metadata(self) -> dict[str, Any]:
        return {
                "bucket": self.bucket, 
                "dominant": self.dominant, 
                "positive": self.positive, 
                **self.extra, 
                }
