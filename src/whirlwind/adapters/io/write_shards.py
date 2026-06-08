"""whirlwind.io.shards 


    PURPOSE:
        - write tile payloads into tar shards 
    BEHAVIOR:
        - create sequential tar files <prefix>-NNN.tar 
        - write two entries per tile <tile_id>.npy and <tile_id>.json 
        - rotate to next shard after shard_size samples 
    PUBLIC:
 
    req = WriteShardRequest(
        out_dir=Path("./artifacts/shards"),
        prefix="mosaic_abc",
        shard_size=4096,
        )

        encoder = TileEncoder(
            mosaic_id="mosaic_abc",
            source_uri="/data/mosaic.tif",
            )

        with ShardWriter(req) as writer:
            for tile in tiles:
                encoded = encoder.encode(tile)
                placement = writer.write(encoded)
                print(placement.shard, placement.key)
        
"""
from __future__ import annotations
import io
import re
import tarfile
import time
import json
import numpy as np
import rasterio
from dataclasses import dataclass, field, replace 
from pathlib import Path
from typing import Optional, Any, Iterator 
from rasterio import Affine



from whirlwind.domain.tile import  EncodedTile


@dataclass
class WriteShardRequest: 
    """ 
    purpose 
    --------
    configuration for shard reading/writing 
    
    usage 
    -------- 
    request = WriteShardRequest(MosaicBranch, Config) 

    behavior 
    -------- 
    builds prefix, shard_size, out_dir from config

    """
    out_dir: Path 
    prefix: str
    shard_size: int 
    start_index: int = 1 

    @classmethod
    def defaults(cls, out_path: Path | str, prefix: str="tile", 
                 size: int = 2048, start_index: int = 1) -> "WriteShardRequest":
        return cls(out_dir=Path(out_path), prefix=prefix, shard_size=size, start_index=start_index )

    @classmethod
    def from_path(cls, out_path: Path | str, prefix: str, size: int) -> "WriteShardRequest": 
        return cls(prefix=prefix, shard_size=size, out_dir=Path(out_path))
    

@dataclass(frozen=True)
class ShardPlacement: 
    """ result of writing one encoded tile """
    tile_id: str 
    key: str 
    shard_path: str 
    shard_index: int 

@dataclass
class ShardWriter:
    """ 
        takes in WriteShardRequest and safely open, make sure path for tar is valid, 
        and for an EncodedTile write each of key.npy and key.json for that tiles bytes 
        Return a ShardPlacement object with pointer to shard and tile key. 

        Input 
        ---------- 
        request: WriteShardRequest(Mosaic_Branch, Config)
        
        Output 
        ---------- 
        self.write(encoded_tile) -> ShardPlacement 

        Usage 
        ---------- 

        encoder = TileEncoder(
            mosaic_id="mosaic_abc",
            source_uri="/data/mosaic.tif",
            )

        with ShardWriter(req) as writer:
            for tile in tiles:
                encoded = encoder.encode(tile)
                placement = writer.write(encoded)
                print(placement.shard, placement.key)
    """ 
    request: WriteShardRequest 
    shard_index: int = field(init=False)
    total_written: int = field(default=0, init=False)

    tar: Optional[tarfile.TarFile] = field(default=None, init=False)
    tar_path: Optional[Path] = field(default=None, init=False) 
    
    def __post_init__(self) -> None: 
        self.request.out_dir.mkdir(parents=True, exist_ok=True)
        self.shard_index = self.request.start_index 
    
    def __enter__(self) -> "ShardWriter":
        return self 

    def __exit__(self, exc_type, exc, tb) -> None: 
        self.close()
    
    def _current_shard_name(self) -> str: 
        return f"{self.request.prefix}-{self.shard_index:03d}.tar"
    
    def _open_next(self) -> None:
        if self.tar is not None:
            self.tar.close()

        self.tar_path = self.request.out_dir / self._current_shard_name()
        self.tar = tarfile.open(self.tar_path, "w")
        self.samples_in_shard = 0 
        self.shard_index += 1 

    def _ensure_open(self) -> None: 
        if self.tar is None:
            self._open_next()
            return 
        if self.samples_in_shard >= self.request.shard_size: 
            self._open_next()

    def _write_member(self, name: str, payload: bytes) -> None: 
        if self.tar is None:
            raise RuntimeError("tar shard is not open; cannot write")

        info = tarfile.TarInfo(name)
        info.size = len(payload)
        info.mtime = int(time.time())
        self.tar.addfile(info, io.BytesIO(payload))

    def write(self, tile: EncodedTile) -> ShardPlacement:
        """
        Write one encoded tile into the current shard.

        Writes:
          <key>.npy
          <key>.json
        """
        self._ensure_open()

        assert self.tar_path is not None

        self._write_member(f"{tile.key}.npy", tile.npy_bytes)
        self._write_member(f"{tile.key}.json", tile.json_bytes)

        self.samples_in_shard += 1
        self.total_written += 1

        return ShardPlacement(
            tile_id=tile.tile_id,
            key=tile.key,
            shard_path=self.tar_path.name,
            shard_index=self.shard_index - 1,
        )

    def close(self) -> None:
        if self.tar is not None:
            self.tar.close()
            self.tar = None
            self.tar_path = None


class RoutedShardWriter:

    """
    used to wrap ShardWriter 

    one child writer is created per label bucket 

    """

    def __init__(self, request: WriteShardRequest) -> None:
        self.request = request
        self.writers: dict[str, ShardWriter] = {}

    def __enter__(self) -> "RoutedShardWriter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def write(self, tile: EncodedTile) -> ShardPlacement:
        bucket = tile.metadata.get("bucket", "shards")
        bucket = self._safe_bucket(bucket)

        writer = self._writer_for(bucket)
        placement = writer.write(tile)

        return replace(
            placement,
            shard_path=str(Path(bucket) / placement.shard_path),
        )

    def _writer_for(self, bucket: str) -> ShardWriter:
        if bucket not in self.writers:
            child_request = replace(
                self.request,
                out_dir=self.request.out_dir / bucket,
                prefix=f"{bucket}_{self.request.prefix}",
            )

            self.writers[bucket] = ShardWriter(child_request)

        return self.writers[bucket]

    def close(self) -> None:
        for writer in self.writers.values():
            writer.close()

    @staticmethod
    def _safe_bucket(bucket: str) -> str:
        bucket = str(bucket).strip().lower()
        bucket = re.sub(r"[^a-z0-9_.-]+", "_", bucket)
        return bucket or "unknown"


@dataclass 
class BinSplitShardWriter: 
    """ 
        router for ShardWriter to direct encoded tiles into split_on and notsplit_on subdirectories 

        input 
        ------ 
        takes a shard request with config, split_on,  tokens and instantiates two new SplitWriteShardRequests  

        output 
        ------ 
        shards in two split bins 

    """

    def __init__(self, request: WriteShardRequest, split_on: str): 
        self.split = split_on
        self.dmg_dir = request.out_dir / f"{split_on}"
        self.ndmg_dir = request.out_dir / f"not{split_on}"
        
        self.dmg_req = WriteShardRequest(prefix=f"{split_on}_{request.prefix}", 
                                    shard_size = request.shard_size, 
                                    out_dir=self.dmg_dir)

        self.ndmg_req = WriteShardRequest(prefix=f"not{split_on}_{request.prefix}", 
                                     shard_size = request.shard_size, 
                                     out_dir=self.ndmg_dir)

        self.dmg_writer = ShardWriter(self.dmg_req)
        self.ndmg_writer = ShardWriter(self.ndmg_req)

    def __enter__(self) -> "BinSplitShardWriter":
        return self 

    def __exit__(self, exc_type, exc, tb) -> None: 
        self.close()

    def write(self, tile: EncodedTile) -> ShardPlacement:
        """ write encoded tile to writer depending on split, defaults to damage """
        metadata = tile.metadata
        damage = metadata["labels"][self.split]
        
        if damage: 
            return self.dmg_writer.write(tile)
        else: 
            return self.ndmg_writer.write(tile)

    def close(self) -> None:
        if self.dmg_writer.tar is not None:
            self.dmg_writer.close()

        if self.ndmg_writer.tar is not None:
            self.ndmg_writer.close()


#########################################
#### SHARD READING ######################

class ReadShardRequest: 
    pass 



def _list_to_affine(v: list[float]) -> Affine:
    return Affine(v[0], v[1], v[2], v[3], v[4], v[5])


def iter_encoded_pairs(shard_path: Path) -> Iterator[tuple[str, bytes, dict[str, Any]]]:
    """
    Stream (key, npy_bytes, metadata) pairs from one shard tar.

    Expected current shard format:
        {key}.npy
        {key}.json
    """
    npy_by_key: dict[str, bytes] = {}
    json_by_key: dict[str, dict[str, Any]] = {}

    with tarfile.open(shard_path, "r") as tar:
        for member in tar:
            if not member.isfile():
                continue

            suffix = Path(member.name).suffix.lower()
            if suffix not in {".npy", ".json"}:
                continue

            key = Path(member.name).stem

            f = tar.extractfile(member)
            if f is None:
                continue

            payload = f.read()

            if suffix == ".npy":
                npy_by_key[key] = payload
            else:
                json_by_key[key] = json.loads(payload.decode("utf-8"))

            if key in npy_by_key and key in json_by_key:
                yield key, npy_by_key.pop(key), json_by_key.pop(key)


def _load_npy(payload: bytes) -> np.ndarray:
    arr = np.load(io.BytesIO(payload), allow_pickle=False)

    # rasterio writes arrays as (bands, height, width)
    if arr.ndim == 2:
        arr = arr[np.newaxis, :, :]

    if arr.ndim != 3:
        raise ValueError(f"expected array shape (bands, height, width), got {arr.shape}")

    return arr


def write_tile_tif(
    arr: np.ndarray,
    metadata: dict[str, Any],
    out_path: Path,
                    ) -> None:
    """
    Turn one EncodedTile pair back into a GeoTIFF.
    """

    count, height, width = arr.shape

    transform = metadata.get("transform")
    if transform is None:
        raise ValueError(f"tile metadata missing transform: {metadata.get('tile_id', out_path.stem)}")

    profile: dict[str, Any] = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": count,
        "dtype": arr.dtype,
        "crs": metadata.get("crs") or None,
        "transform": _list_to_affine(transform),
        "compress": "deflate",
        "tiled": True,
    }

    if width >= 16 and height >= 16:
        profile["blockxsize"] = min(256, width)
        profile["blockysize"] = min(256, height)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(arr)


def shard_to_tifs(shard_path: Path | str, out_dir: Path | str) -> int:
    """
    Convert one shard tar into individual GeoTIFF tiles.
    """
    shard_path = Path(shard_path)
    out_dir = Path(out_dir)

    n = 0
    for key, npy_bytes, metadata in iter_encoded_pairs(shard_path):
        arr = _load_npy(npy_bytes)

        tile_id = metadata.get("tile_id") or key
        out_path = out_dir / f"{tile_id}.tif"

        write_tile_tif(arr, metadata, out_path)
        n += 1

    return n


def shard_dir_to_tifs(
    shard_dir: Path | str,
    out_dir: Path | str,
    pattern: str = "*.tar",
) -> int:
    """
    Convert a directory of shard tars into GeoTIFF tiles.

    Handles normal shards and split shards if pointed at:
        shards/
        shards/inside/
        shards/outside/
    """
    shard_dir = Path(shard_dir)
    out_dir = Path(out_dir)

    total = 0

    for shard_path in sorted(shard_dir.glob(pattern)):
        shard_out = out_dir / shard_path.stem
        total += shard_to_tifs(shard_path, shard_out)

    return total
