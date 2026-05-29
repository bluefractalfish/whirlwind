from dataclasses import dataclass 
from typing import Iterable 
from pathlib import Path

from whirlwind.adapters.io.idmanifest import IDManifest
from whirlwind.commands.bridge import TokenView
from whirlwind.commands.context import CommandContext
from whirlwind.domain.mosaic import MosaicRecord




def selector(tv: TokenView) -> MosaicSelector:
    limit_values = tv.values("--limit")
    limit = int(limit_values[-1]) if limit_values else None

    return MosaicSelector(
        mosaic_ids=tv.values("--mosaic", "--mosaic-id"),
        variants=tv.values("--variant"),
        dates=tv.values("--date"),
        metamosaic_ids=tv.values("--metamosaic", "--metamosaic-id"),
        limit=limit,
    )

def pathset(tv: TokenView, context: CommandContext) -> tuple[Iterable[Path], IDManifest]:
    """ given a tokenview and command context,
        
        1) select mosaic paths from token view using MosaicSelector 
        2) build manifest from command_context run tree 
        3) return paths, manifest for paths selected from that manifest 

        """
    select = selector(tv)
    manifest_p = context.run_tree.get_manifest_path_csv() 
    manifest = IDManifest(manifest_p)  
    return select.paths_from(manifest), manifest 


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

    def paths_from(self, manifest: IDManifest) -> Iterable[Path]: 

        records = [record for record in manifest.records()
                   if self.matches(record)]

        if self.limit is not None: 
            records = records[:self.limit] 

        return [record.path for record in records]
