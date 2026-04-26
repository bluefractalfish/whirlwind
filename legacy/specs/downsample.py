
from dataclasses import dataclass, asdict, fields 
from typing import Literal, Any
from whirlwind.domain.config.schema import Config 

@dataclass(frozen=True)
class DisplaySpec:
    """
    Visual stretch settings for browse/downsample rasters.

    This is for display products only. It should not control analytical tile
    quantization.
    """

    enabled: bool = True
    method: Literal["none", "minmax", "percentile"] = "percentile"
    p_low: float = 2.0
    p_high: float = 98.0
    dst_min: float = 1.0
    dst_max: float = 255.0
    sample_windows: int = 512
    sample_size: int = 256

    def to_record(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, raw: dict[str, Any] | None) -> "DisplaySpec":
        if raw is None:
            return cls()

        valid_fields = {f.name for f in fields(cls)}
        values = {
            k: v
            for k, v in raw.items()
            if k in valid_fields and v is not None
        }

        if "enabled" in values:
            values["enabled"] = bool(values["enabled"])

        if "method" in values:
            values["method"] = str(values["method"]).lower()

        if "p_low" in values:
            values["p_low"] = float(values["p_low"])

        if "p_high" in values:
            values["p_high"] = float(values["p_high"])

        if "dst_min" in values:
            values["dst_min"] = float(values["dst_min"])

        if "dst_max" in values:
            values["dst_max"] = float(values["dst_max"])

        if "sample_windows" in values:
            values["sample_windows"] = int(values["sample_windows"])

        if "sample_size" in values:
            values["sample_size"] = int(values["sample_size"])

        spec = cls(**values)
        spec.validate()
        return spec

    def validate(self) -> None:
        if self.method not in ("none", "minmax", "percentile"):
            raise ValueError(f"unsupported display method: {self.method}")

        if self.method == "percentile":
            if not 0 <= self.p_low < self.p_high <= 100:
                raise ValueError(
                    "display percentile stretch requires 0 <= p_low < p_high <= 100"
                )

        if self.dst_max <= self.dst_min:
            raise ValueError("display dst_max must be greater than dst_min")

        if self.sample_windows <= 0:
            raise ValueError("display sample_windows must be > 0")

        if self.sample_size <= 0:
            raise ValueError("display sample_size must be > 0")


@dataclass(frozen=True)
class DSSpec:
    """
    Downsample params for gdal_translate.

    DisplaySpec controls optional visual stretching for browse rasters.
    """

    target_resolution: tuple[float, float] | None = None
    scale_factor: float | None = None
    target_width: int | None = None
    target_height: int | None = None
    resampling: str = "nearest"
    dtype: str | None = None
    compression: str = "DEFLATE"
    tiled: bool = True
    overview_levels: list[int] | str = "AUTO"
    nodata: float | None = None
    preserve_bounds: bool = False
    display: DisplaySpec = DisplaySpec()

    def to_record(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_config(cls, config: Config) -> "DSSpec":
        raw = config.parse("operations", "downsample") or {}

        display = DisplaySpec.from_mapping(raw.get("display"))

        valid_fields = {f.name for f in fields(cls)}
        values: dict[str, Any] = {
            k: v
            for k, v in raw.items()
            if k in valid_fields and k != "display" and v is not None
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

        values["display"] = display

        spec = cls(**values)
        spec.validate()
        return spec

    def validate(self) -> None:
        strategies = [
            self.target_resolution is not None,
            self.scale_factor is not None,
            self.target_width is not None or self.target_height is not None,
        ]

        if sum(bool(x) for x in strategies) != 1:
            raise ValueError(
                "DSSpec requires exactly one sizing strategy: "
                "target_resolution, scale_factor, or target_width/target_height"
            )

        if self.scale_factor is not None and self.scale_factor <= 0:
            raise ValueError("scale_factor must be > 0")

        if self.target_resolution is not None:
            xres, yres = self.target_resolution
            if xres <= 0 or yres <= 0:
                raise ValueError("target_resolution values must be > 0")
