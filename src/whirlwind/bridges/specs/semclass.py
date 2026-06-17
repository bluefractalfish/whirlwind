from pathlib import Path 
from dataclasses import dataclass
from typing import Literal
from whirlwind.adapters.display.colorcontrols import ArrayLayout

BucketMode = Literal["mostly", "hybrid"]

@dataclass(frozen=True)
class SCSpec:

    # RemoteCLIP model loading

    model_name: str = "ViT-B-32"
    hf_repo: str = "chendelong/RemoteCLIP"
    checkpoint_path: Path | None = None
    cache_dir: Path = Path("~/.cache/whirlwind/remoteclip")

    # Use "cuda" when available, otherwise "cpu".
    device: str = "cpu"

    # ------------------------------------------------------------------
    # Tile array -> RGB image conversion
    # ------------------------------------------------------------------

    # Use "chw" tile arrays are shaped like:
    #   (bands, height, width)
    #
    # Use "hwc" if tile arrays are shaped like:
    #   (height, width, bands)
    layout: ArrayLayout = "chw"

    # These are the bands used to make the RGB preview passed to RemoteCLIP.
    #   zero indexed 
    rgb_bands: tuple[int, int, int] = (0, 1, 2)

    # Percentile stretch before converting to uint8.
    # This matters a lot for aerial imagery because raw uint16/float tiles
    # may otherwise look mostly black, white, or low-contrast to RemoteCLIP.
    percentile_low: float = 2.0
    percentile_high: float = 98.0
    
    #logit 
    logit_scale: float = 100.0
    # ------------------------------------------------------------------
    # Optional runtime behavior
    # ------------------------------------------------------------------

    log_decisions: bool = True 
