
"""
conceptually: 
    shards/ 
        shards-001.tar 
            abc.npy 
            abc.json 
            def.npy 
            def.json 
        
        |
        V 
    ShardReader : reads tar files and reconstructs npy/json pairs  
        |
        V
        abc.npy + abc.json 
        def.npy + def.json 
        |
        V 
    TileDecoder : turns npy bytes + json bytes into in memory tile object 
        |
        V
        key 
        array 
        metadata 
        |
        V 
    TileRenderer : converts raw tile array into display-ready or raw output array 
        |
        V

        raw --> array 
        or 
        display --> RGB uint array
        |
        V
    GeoTiffWriter : writes the array + georeferenced data into .tif 
        |
        V
        abc.tif 
        def.tif 

"""

import json 
import tarfile 
import numpy as np 
import rasterio 
from typing import Literal, Any, Iterator
from pathlib import Path

from whirlwind.domain.tile import EncodedBundle 
from whirlwind.adapters.io.write_shards import iter_encoded_pairs
from whirlwind.adapters.display.colorcontrols import to_rgb, to_rgba, interpret_colors, blend_rgb_overlay

ExportMode = Literal["display", "raw"] 
DisplayKind = Literal["rgb", "rgba"] 


ColorBy = Literal["centerline_distance"] 
 
def convert_to_tif(
        shard_path: Path | str, 
        out_dir: Path | str, 
        *, 
        mode: ExportMode,
        display_kind: DisplayKind,
        display_bands: tuple[int, int, int] | None, 
        alpha_band: int, 
        p_low: float, 
        p_high: float, 
        compress: str | None, 
        stop_on_error: bool, 
        color_by: ColorBy | None=None, 
        distance_max: float | None=None, 
        alpha: float,
        debug: bool = False, 
        one_tif_per_npy: bool 
        ) -> tuple[int, int, int]: 

    """
            for each tar in shard_dir: 

                output_dir = out_dir 

                for each TilePair in read_tile_pairs(tar file):
                    try: 
                        decoded = TilePair.decode() 

                        if mode is raw: 
                            out_array = render_raw (decoded.array)

                        if mode is display: 
                            out_array = render_rgb(decoded.array)

                        out_path = out_dir / decoded.tile_id + ".tif"

                        
                        write_tile(
                            out_array, 
                            decoded.metadata, 
                            out_path 
                        )

    """ 


    shard_path = Path(shard_path) 
    out_dir = Path(out_dir) 

    tiles_seen = 0 
    tiles_written = 0 
    errors = 0 
    
    if one_tif_per_npy and mode != "raw":
        raise ValueError("for one_tif_per_npy only mode=raw supported")

    if color_by == "centerline_distance" and distance_max is None:
        distance_max = max_damage_distance(shard_path)

    for pair in iter_encoded_pairs(shard_path):
        tiles_seen += 1 
        
        if one_tif_per_npy: 
            try: 
                written, member_errors = (
                        write_npy_members(
                            pair, 
                            out_dir, 
                            compress=compress, 
                            stop_on_error=stop_on_error, 
                            debug=debug
                            )
                        ) 
                tiles_written += written 
                errors += member_errors 
            except Exception: 
                errors += 1 
                if stop_on_error: 
                    raise 
                continue 
        if not one_tif_per_npy:
            try: 
                write_tile(
                        pair,
                        out_dir,
                        mode=mode, 
                        display_kind=display_kind, 
                        display_bands=display_bands, 
                        alpha_band=alpha_band, 
                        p_low=p_low, 
                        p_high=p_high, 
                        compress=compress, 
                        color_by=color_by, 
                        distance_max=distance_max,
                        alpha=alpha, 
                        debug=debug
                    )
                tiles_written += 1 

            except Exception: 
                errors += 1 
                if stop_on_error:
                    raise 
    return tiles_seen, tiles_written, errors 



def max_damage_distance(shard_path: Path | str) -> float | None:
    """
    Return max labels.distance_to_center_line across one shard.

    """
    shard_path = Path(shard_path)
    max_dist: float | None = None

    with tarfile.open(shard_path, "r") as tar:
        for member in tar:
            if not member.isfile():
                continue

            if Path(member.name).suffix.lower() != ".json":
                continue

            f = tar.extractfile(member)
            if f is None:
                continue

            metadata = json.loads(f.read().decode("utf-8"))
            labels = metadata.get("labels") or {}
            dist = labels.get("distance_to_center_line")

            if dist is None:
                continue

            try:
                d = float(dist)
            except (TypeError, ValueError):
                continue

            if not np.isfinite(d):
                continue

            max_dist = d if max_dist is None else max(max_dist, d)

    return max_dist

def distance_to_rgb_tile(
    metadata: dict[str, Any],
    *,
    height: int,
    width: int,
    max_distance: float | None,
    gamma: float = 0.65
) -> np.ndarray:
    """
    Build a 3-band uint8 RGB tile from labels.distance_to_center_line.

    Color rule:
        missing distance -> gray
        near line        -> red
        far from line    -> blue
    """
    labels = metadata.get("labels") or {}
    dist = labels.get("distance_to_center_line")
    if dist is None or max_distance is None or max_distance <= 0:
        rgb = np.array([128, 128, 128], dtype=np.uint8)
    else:
        d = float(dist)

        t = np.clip(d / max_distance, 0.0, 1.0)
        t = t ** gamma

        red = int(round((1.0 - t) * 255))
        green = 0
        blue = int(round(t * 255))

        rgb = np.array([red, green, blue], dtype=np.uint8)

    out = np.empty((3, height, width), dtype=np.uint8)
    out[0].fill(rgb[0])
    out[1].fill(rgb[1])
    out[2].fill(rgb[2])

    return out

def write_npy_members(
    pair: EncodedBundle,
    out_dir: Path,
    *,
    compress: str | None,
    stop_on_error: bool,
    debug: bool = False,
) -> tuple[int, int]:
    """
    write every NPY member/array as an independent GeoTIFF.

    New bundle members are two-dimensional and therefore produce
    single-band TIFFs interpreted as greyscale .
    """
    members = pair.load_npy_bundle() 
    layers = pair.metadata.get("layers") or {}

    tile_id = (
        pair.metadata.get("tile_id")
        or pair.key
    )

    written = 0
    errors = 0

    for suffix, array in members.items():
        try:
            if debug:
                _debug_arr(
                    f"member {suffix}",
                    array,
                    pair.key,
                )

            if array.ndim == 2:
                array = array[
                    np.newaxis,
                    :,
                    :,
                ]

            if array.ndim != 3:
                raise ValueError(
                    "expected NPY member shape "
                    "(height, width) or "
                    "(bands, height, width), "
                    f"got {array.shape}"
                )

            if suffix:
                tif_name = (
                    f"{tile_id}.{suffix}.tif"
                )
            else:
                # Legacy one-NPY shard.
                tif_name = f"{tile_id}.tif"

            out_path = out_dir / tif_name

            profile = pair.profile(
                arr=array,
                compress=compress,
            )

            # Do not automatically set profile["nodata"] here.
            # A fill value of zero is ambiguous because zero may also
            # be valid CHM, DEM, NDVI, or image data.
            out_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            layer = layers.get(suffix) or {}

            with rasterio.open(
                out_path,
                "w",
                **profile,
            ) as destination:
                destination.write(array)

                if array.shape[0] == 1 and suffix:
                    destination.set_band_description(
                        1,
                        suffix,
                    )

                # Preserve the fill/mask information as ordinary
                # metadata without causing GDAL to mask valid zeros.
                destination.update_tags(
                    layer_suffix=suffix,
                    mosaic_id=str(
                        layer.get("mosaic_id") or ""
                    ),
                    variant_token=str(
                        layer.get("variant_token")
                        or layer.get("variant_id")
                        or ""
                    ),
                    source_band=str(
                        layer.get("source_band") or ""
                    ),
                    source_uri=str(
                        layer.get("source_uri") or ""
                    ),
                    fill_value=str(
                        layer.get("fill_value")
                        if layer.get("fill_value")
                        is not None
                        else ""
                    ),
                    masked_pixel_count=str(
                        layer.get(
                            "masked_pixel_count",
                            "",
                        )
                    ),
                )

            written += 1

        except Exception:
            errors += 1

            if stop_on_error:
                raise

    return written, errors

def write_tile(
        pair: EncodedBundle,
        out_dir: Path, 
        *, 
        mode: ExportMode, 
        display_kind: DisplayKind, 
        alpha_band: int, 
        p_low: float, 
        p_high: float, 
        debug: bool, 
        display_bands: tuple[int, int, int] | None=None, 
        compress: str | None=None, 
        color_by: ColorBy | None=None, 
        distance_max: float | None=None, 
        alpha: float, 
        ) -> None: 
    """ 
        write one EncodedPair as a Geotiff 

        args: 
            pair: EncodedPair 
            out_path: destination of .tif 
            mode: 
                "display" -> write qgis friendly uint8 display tiff 
                "raw" -> preserve array dtype and values 
            dusplay_kind: 
                "rgb" -> write 3 band rgb, safest for qgis 
                "rgba" -> write with alpha 
            display_band: 
                zero-indexed rgb source bands 
                    example: 
                        (0,1,2) RGB 
                        (2,1,0) BGR -> RGB 
                        (3,0,1) false color 
            alpha_band: zero indexed alpha source band for display_kind=rgba 

            p_low/p_high: percentile stretch rangfe for rgb bands 
            compress: none means no compression
                examples: "deflate", "lzw" 

    """
    arr = pair.load_npy_tile()  
    if debug:
        _debug_arr("loaded from shard", arr, pair.key)

    out_path = pair.tile_out_path(out_dir)  

    if arr.ndim == 2:
        arr = arr[np.newaxis, :, :]
 
    if arr.ndim != 3:
        raise ValueError(f"expected array shape (bands, height, width), got {arr.shape}")

    if color_by == "centerline_distance":
        _, height, width = arr.shape

        base_rgb = to_rgb(
            arr,
            display_bands=display_bands,
            p_low=p_low,
            p_high=p_high,
        )

        overlay_rgb = distance_to_rgb_tile(
            pair.metadata,
            height=height,
            width=width,
            max_distance=distance_max,
        )

        arr = blend_rgb_overlay(
            base_rgb,
            overlay_rgb,
            alpha=alpha,
        )

    elif mode == "display":
        if display_kind == "rgb":
            arr = to_rgb(
                arr,
                display_bands=display_bands,
                p_low=p_low,
                p_high=p_high,
            )

        elif display_kind == "rgba":
            arr = to_rgba(
                arr,
                display_bands=display_bands,
                alpha_band=alpha_band,
                p_low=p_low,
                p_high=p_high,
            )

        else:
            raise ValueError(f"unknown display kind: {display_kind}")

    elif mode == "raw":
        # Preserve all bands and original dtype
        pass

    else:
        raise ValueError(f"unknown export mode: {mode}")

    profile = pair.profile(arr=arr, compress=compress)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(arr)
        interpret_colors(dst, arr)


def _debug_arr(label: str, arr: np.ndarray, key: str) -> None:
    print(f"\n[{key}] {label}")
    print("  shape:", arr.shape)
    print("  dtype:", arr.dtype)
    print("  min:", np.nanmin(arr))
    print("  max:", np.nanmax(arr))
    print("  nonzero:", np.count_nonzero(arr), "of", arr.size)

    if arr.ndim == 3:
        for b in range(arr.shape[0]):
            band = arr[b]
            print(
                f"  band {b}:",
                "min", np.nanmin(band),
                "max", np.nanmax(band),
                "mean", np.nanmean(band),
                "nonzero", np.count_nonzero(band),
            )
