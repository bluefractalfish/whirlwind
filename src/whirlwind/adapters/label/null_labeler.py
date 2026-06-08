
from dataclasses import dataclass, field
from typing import Any
from whirlwind.domain.tile import Tile
from whirlwind.adapters.label.simple_label import SimpleLabel

class UnaryLabeler:
    """
    Labeler used when you do not want real labels.
    
    usage:
    ------- 
    labeler = UnaryLabeler(bucket="tiles")
    Every tile receives the same bucket.

    output:
    -------
        shards/
          tiles/
            shard-000000.tar
    """

    def __init__(self, bucket: str = "tiles") -> None:
        self.bucket = bucket

    def label(self, tile: Tile) -> SimpleLabel:
        return SimpleLabel(
            bucket=self.bucket,
            dominant=self.bucket,
            positive=None,
            extra={
                "labeler": "unary",
            },
        )
