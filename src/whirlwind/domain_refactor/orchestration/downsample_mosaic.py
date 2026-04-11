

from dataclasses import dataclass
from pathlib import Path

from whirlwind.geometry.mosaic import MOSAIC
from whirlwind.repositories.protocols import MosaicRepoProtocol, RasterRepoProtocol
from whirlwind.specs.downsample import DSSpec
from whirlwind.operations.inspect_mosaic import InspectMosaicOp
from whirlwind.operations.downsample_mosaic import DownsampleMosaicOp


@dataclass(frozen=True)
class DownsampleRequest:
    input_uri: str 
    output_uri: str 
    spec: DSSpec

@dataclass(frozen=True)
class DownsampleResult:
    source: MOSAIC 
    downsampled: MOSAIC 


class DownsampleWorkflow:
    def __init__(
            self, 
            mosaic_repo: MosaicRepoProtocol,
            raster_repo: RasterRepoProtocol,
            inspect_op: InspectMosaicOp,
            downsample_op: DownsampleMosaicOp,
            ) -> None:
        self.mosaic_repo = mosaic_repo 
        self.raster_repo = raster_repo 
        self.inspect_op = inspect_op 
        self.downsample_op = downsample_op 
    def run(self, request: DownsampleRequest) -> DownsampleResult:
        source = self.mosaic_repo.get_by_uri(request.input_uri)
        if source is None:
            source = self.inspect_op.run(request.input_uri)
            self.mosaic_repo.put(source)
        downsampled = self.downsample_op.run(
                mosaic=source, 
                output_uri=request.output_uri,
                spec = request.spec
            )
        self.mosaic_repo.put(downsampled)

        return DownsampleResult(source=source, downsampled=downsampled)

