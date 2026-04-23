
from dataclasses import dataclass, asdict, fields 
from typing import Optional, Dict, Any, Tuple, Union, List
from whirlwind.config.schema import Config 

@dataclass
class DSSpec:
    """downsample params for gdal_translate or rasterio_resample"""
    target_resolution: Optional[Tuple[float, float]] = None
    scale_factor: Optional[float] = None
    target_width: Optional[int] = None
    target_height: Optional[int] = None
    resampling: str = "nearest"
    dtype: Optional[str] = None
    compression: str = "DEFLATE"
    tiled: bool = True
    overview_levels: Union[List[int], str] = "AUTO"
    nodata: Optional[float] = None
    preserve_bounds: bool = False

    def to_record(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_config(cls, config: Config) -> "DSSpec":
        raw = config.parse("mosaic", "downsample") or {}

        valid_fields = {f.name for f in fields(cls)}
        values: dict[str, Any] = {
            k: v for k, v in raw.items()
            if k in valid_fields and v is not None
        }

        if "target_resolution" in values:
            xres, yres = values["target_resolution"]
            values["target_resolution"] = (float(xres), float(yres))

        if "scale_factor" in values:
            values["scale_factor"] = float(values["scale_factor"])

        if "target_width" in values:
            values["target_width"] = int(values["target_width"])

        if "target_height" in values:
            values["target_height"] = int(values["target_height"])

        if "nodata" in values:
            values["nodata"] = float(values["nodata"])

        if "overview_levels" in values and values["overview_levels"] != "AUTO":
            values["overview_levels"] = [int(v) for v in values["overview_levels"]]

        return cls(**values)  

