
from dataclasses import dataclass
from typing import Literal
from whirlwind.adapters.display.colorcontrols import ArrayLayout

BucketMode = Literal["mostly", "hybrid"]

@dataclass(frozen=True) 
class SCSpec: 
    cache_dir: str = "~/.cache/remoteclip"
    model_name: str = "ViT-B-32"
    checkpoint_path: str | None = None 
    hf_repo: str = "chendelong/RemoteCLIP"
    device: str = "cpu" 

    layout: ArrayLayout = "chw" 
    rgb_bands: tuple[int, int, int] = (0,1,2)
    percentile_low: float = 2.0 
    percentile_high: float = 98.0 
    bucket_mode: BucketMode = "hybrid"
    mostly_threshold: float = 0.50 
    hybrid_second_threshold: float = 0.45
    

    # prefer structures if close to roads/dirt/shadow 
    # prevents roofs from falling into road/dirt-like class 
    prefer_structures: bool = True 
    structure_margin: float = 0.12 
    min_structure_score: float = 0.16 

    # staging classifier behavior
    review_gap: float = 0.035
    review_min_top_score: float = 0.14

    # roads over dirt/grass/crops when road-like evidence exists
    prefer_roads: bool = True
    road_margin: float = 0.12
    min_road_score: float = 0.10
    min_linear_road_evidence: float = 0.08

    # water over roads/shadow/dirt only when reasonably strong
    prefer_water: bool = True
    water_margin: float = 0.08
    min_water_score: float = 0.10

    # debris override
    prefer_debris: bool = True
    debris_margin: float = 0.18
    min_debris_score: float = 0.035
        
