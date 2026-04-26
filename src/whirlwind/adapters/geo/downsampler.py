"""
whirlwind.adapters.geo.downsample

Lowest-layer GDAL adapter for creating browse/downsampled GeoTIFFs.

PURPOSE 
-------
- Convert a source raster into a smaller browse raster.
- Use `gdal_translate` through subprocess.
- Avoid loading the full raster into Python memory.

PUBLIC 
-------- 




USAGE 
-------- 
Downsampler.from_paths(src_path = source_path, 
                        out_path=browse_path, 
                        spec = ds_spec 
                        )

result = downsampler.run(overwrite=True)

"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any 
import math
import numpy as np
import rasterio
from rasterio.windows import Window
from osgeo import gdal


from whirlwind.bridges.specs.downsample import DSSpec, DisplaySpec




@dataclass(frozen=True)
class Downsampler:
    """ 
    constructs command to dispatch as subprocess with gdal_translate 

    PUBLIC 
    ------- 
    contents 
    ------- 
    src_path: Path 
    out_path: Path 
    spec: DSSpec 

    """
    src_path: Path
    out_path: Path
    spec: DSSpec

    @classmethod
    def from_paths(
        cls,
        src_path: str | Path,
        out_path: str | Path,
        spec: DSSpec,
    ) -> "Downsampler":
        return cls(
            src_path=Path(src_path).expanduser().resolve(),
            out_path=Path(out_path).expanduser().resolve(),
            spec=spec,
        )

    def run(self, *, overwrite: bool = False,  
            disp_range: bool = False, 
            quiet: bool = True ) -> tuple[int, str] :
        self._validate_source()


        self.out_path.parent.mkdir(parents=True, exist_ok=True)

        if self.out_path.exists():
            if overwrite:
                if self.out_path.is_file():
                    self.out_path.unlink()
                else:
                    raise IsADirectoryError(
                        f"output path exists and is not a file: {self.out_path}"
                    )
            else:
                raise FileExistsError(f"output already exists: {self.out_path}")
            if self.out_path.exists() and not overwrite:
                raise FileExistsError(f"downsample output already exists: {self.out_path}")


        cmd = build_gdal_translate_command(
            src_path=self.src_path,
            out_path=self.out_path,
            spec=self.spec,
            calculate_display_range=disp_range, 
            quiet=quiet 
        )

        try:
                completed = subprocess.run(
                cmd,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                "gdal_translate failed\n\n"
                f"command:\n{_cmd_str(cmd)}\n\n"
                f"return code:\n{exc.returncode}\n\n"
                f"stdout:\n{exc.stdout or ''}\n\n"
                f"stderr:\n{exc.stderr or ''}"
            ) from exc

        return completed.returncode, _cmd_str(cmd) 
        


    def _validate_source(self) -> None:
        gdal.UseExceptions()

        if not self.src_path.exists():
            raise FileNotFoundError(f"source raster does not exist: {self.src_path}")

        ds = gdal.Open(str(self.src_path), gdal.GA_ReadOnly)
        if ds is None:
            raise RuntimeError(f"GDAL failed to open source raster: {self.src_path}")

        ds = None


def build_gdal_translate_command(
    *,
    src_path: Path,
    out_path: Path,
    spec: DSSpec,
    calculate_display_range: bool = False, 
    quiet: bool = False
) -> list[str]:
    """
    Build a gdal_translate command for memory-safe browse raster creation.

    This does not read the full raster into Python. GDAL performs the raster IO.
    """

    cmd: list[str] = ["gdal_translate",  "-of", "GTiff"]
    
    if quiet: 
        cmd.append("-q")


    if spec.dtype:
        cmd += ["-ot", str(spec.dtype)]

    # calculate max/pin percent using estimate_display range
    # avoids clipping on downsampling 

    if calculate_display_range:  
        display_range = estimate_display_range(src_path, spec.display)
        if display_range is not None: 
            src_min, src_max = display_range 
            cmd += [
                    "-scale", 
                    str(src_min), 
                    str(src_max), 
                    str(spec.display.dst_min), 
                    str(spec.display.dst_max),
                ]

    cmd += _size_args(spec)

    if spec.resampling:
        cmd += ["-r", str(spec.resampling)]

    if spec.nodata is not None:
        cmd += ["-a_nodata", str(spec.nodata)]

    for creation_option in _creation_options(spec):
        cmd += ["-co", creation_option]

    # Preserve source metadata domains when supported by the installed GDAL.
    cmd += ["--config", "GDAL_TRANSLATE_COPY_SRC_MDD", "YES"]

    cmd += [str(src_path), str(out_path)]

    return cmd


def _size_args(spec: DSSpec) -> list[str]:
    """
    Resolve output size strategy.

    prioritize in order 
    1. target_resolution -> -tr xres yres
    2. scale_factor      -> -outsize pct% pct%
    3. target dimensions -> -outsize width height

    Exactly one strategy should be active.
    """

    strategies = [
        spec.target_resolution is not None,
        spec.scale_factor is not None,
        spec.target_width is not None or spec.target_height is not None,
    ]

    if sum(bool(x) for x in strategies) != 1:
        raise ValueError(
            "DSSpec must define exactly one downsample sizing strategy: "
            "target_resolution, scale_factor, or target_width/target_height"
        )

    if spec.target_resolution is not None:
        xres, yres = spec.target_resolution
        return ["-tr", str(float(xres)), str(float(yres))]

    if spec.scale_factor is not None:
        if spec.scale_factor <= 0:
            raise ValueError("scale_factor must be > 0")

        pct = spec.scale_factor * 100.0
        pct_s = _format_percent(pct)
        return ["-outsize", f"{pct_s}%", f"{pct_s}%"]

    width = "0" if spec.target_width is None else str(int(spec.target_width))
    height = "0" if spec.target_height is None else str(int(spec.target_height))

    if width == "0" and height == "0":
        raise ValueError("target_width and target_height cannot both be null/0")

    return ["-outsize", width, height]


def _creation_options(spec: DSSpec) -> list[str]:
    opts: list[str] = []

    if spec.compression:
        opts.append(f"COMPRESS={spec.compression}")

    if spec.tiled:
        opts.append("TILED=YES")

    return opts


def _format_percent(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.6g}"


def estimate_display_range(
    src_path: str | Path,
    spec: DisplaySpec,
    *,
    band: int = 1,
    ) -> tuple[float, float] | None:

    """
    Estimate display source range from sampled windows.

    """

    if not spec.enabled or spec.method == "none":
        return None

    src_path = Path(src_path).expanduser().resolve()

    samples: list[np.ndarray] = []

    with rasterio.open(src_path) as ds:
        width = ds.width
        height = ds.height

        sample_size = min(spec.sample_size, width, height)
        if sample_size <= 0:
            return None

        tiles_x = max(1, width // sample_size)
        tiles_y = max(1, height // sample_size)
        total_tiles = tiles_x * tiles_y

        step = max(1, int(math.sqrt(total_tiles / max(1, spec.sample_windows))))

        sampled = 0

        for ty in range(0, tiles_y, step):
            y = min(ty * sample_size, height - sample_size)

            for tx in range(0, tiles_x, step):
                x = min(tx * sample_size, width - sample_size)

                win = Window(
                    col_off=x,
                    row_off=y,
                    width=sample_size,
                    height=sample_size,
                )

                arr = ds.read(
                    band,
                    window=win,
                    masked=True,
                    out_dtype="float32",
                )

                if np.ma.isMaskedArray(arr):
                    vals = arr.compressed()
                else:
                    vals = arr.ravel()

                vals = vals[np.isfinite(vals)]

                if vals.size:
                    samples.append(vals)

                sampled += 1
                if sampled >= spec.sample_windows:
                    break

            if sampled >= spec.sample_windows:
                break

    if not samples:
        return None

    values = np.concatenate(samples)

    if values.size == 0:
        return None

    if spec.method == "minmax":
        src_min = float(np.min(values))
        src_max = float(np.max(values))
    elif spec.method == "percentile":
        src_min = float(np.percentile(values, spec.p_low))
        src_max = float(np.percentile(values, spec.p_high))
    else:
        raise ValueError(f"unsupported display stretch method: {spec.method}")

    if not np.isfinite(src_min) or not np.isfinite(src_max) or src_max <= src_min:
        return None

    return src_min, src_max


def _cmd_str(cmd: list[str]) -> str:
    return " ".join(str(x) for x in cmd)

