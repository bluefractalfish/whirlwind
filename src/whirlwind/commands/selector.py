from dataclasses import dataclass 
from whirlwind.commands.bridge import TokenView
from whirlwind.domain.geometry.mosaics.mosaic import MosaicRecord

def selector_from_tokens(tv: TokenView) -> MosaicSelector:
    limit_values = tv.values("--limit")
    limit = int(limit_values[-1]) if limit_values else None

    return MosaicSelector(
        mosaic_ids=tv.values("--mosaic", "--mosaic-id"),
        variants=tv.values("--variant"),
        dates=tv.values("--date"),
        metamosaic_ids=tv.values("--metamosaic", "--metamosaic-id"),
        limit=limit,
    )

@dataclass(frozen=True)
class MosaicSelector:
    mosaic_ids: tuple[str, ...] = ()
    variants: tuple[str, ...] = ()
    dates: tuple[str, ...] = ()
    metamosaic_ids: tuple[str, ...] = ()
    limit: int | None = None

    def matches(self, record: MosaicRecord) -> bool:
        if self.mosaic_ids and record.mosaic_id not in self.mosaic_ids:
            return False
        if self.variants and record.variant_id not in self.variants:
            return False
        if self.dates and record.date not in self.dates:
            return False
        if self.metamosaic_ids and record.metamosaic_id not in self.metamosaic_ids:
            return False
        return True
