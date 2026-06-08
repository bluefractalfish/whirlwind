
from dataclasses import dataclass
from typing import Literal


ArrayLayout = Literal["auto", "chw", "hwc"]
BucketMode = Literal["mostly", "hybrid"]

@dataclass(frozen=True) 
class SCSpec: 
    cache_dir: str
    model_name: str = "ViT-B-32"
    checkpoint_path: str | None = None 
    hf_repo: str = "chendelong/RemoteCLIP"
    device: str = "cpu" 

    layout: ArrayLayout = "chw" 
    rgb_bands: tuple[int, int, int] = (0,1,2)
    percentile_low: float = 2.0 
    percentile_high: float = 98.0 
    bucket_mode: BucketMode = "hybrid"
    mostly_threshold: float = 0.60 
    hybrid_second_threshold: float = 0.25
    

    # prefer structures if close to roads/dirt/shadow 
    # prevents roofs from falling into road/dirt-like class 
    prefer_structures: bool = True 
    structure_margin: float = 0.08 
    min_structure_score: float = 0.22 
    
