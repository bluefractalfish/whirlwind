
from dataclasses import dataclass
from typing import Iterator

from whirlwind.adapters.io.idmanifest import IDManifest
from whirlwind.domain.geometry.mosaics.mosaic import MosaicRecord
from whirlwind.domain.geometry.mosaics.mosaic import MosaicSelector

@dataclass(frozen=True)
class MosaicCatalog:
    manifest: IDManifest

    def records(self) -> Iterator[MosaicRecord]:
        yield from self.manifest.records()

    def select(self, selector: MosaicSelector) -> Iterator[MosaicRecord]:
        for record in self.records():
            if selector.matches(record):
                yield record
