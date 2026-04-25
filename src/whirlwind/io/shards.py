"""whirlwind.io.shards 


    PURPOSE:
        - write tile payloads into tar shards 
    BEHAVIOR:
        - create sequential tar files <prefix>-NNN.tar 
        - write two entries per tile <tile_id>.npy and <tile_id>.json 
        - rotate to next shard after shard_size samples 
    PUBLIC:
 
    req = ShardRequest(
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
import tarfile
import time
from dataclasses import dataclass, field 
from pathlib import Path
from typing import Optional


from whirlwind.config import Config 
from whirlwind.geometry.tile import Tile, EncodedTile
from whirlwind.filetrees.mosaicbranch import MosaicBranch


@dataclass
class ShardRequest: 
    """ 
    purpose 
    --------
    configuration for shard writing 
    
    usage 
    -------- 
    request = ShardRequest(MosaicBranch, Config) 

    behavior 
    -------- 
    builds prefix, shard_size, out_dir from config

    """
    out_dir: Path 
    prefix: str
    shard_size: int 
    start_index: int = 1 

    def __init__(self, branch: MosaicBranch | None=None, 
                 config: Config | None=None, 
                 prefix: str | None=None, 
                 shard_size: int | None=None, 
                 out_dir: Path | str | None=None ) -> None : 

        if config is not None:
            shatter_config = config.parse("mosaic","shatter")
            self.prefix = shatter_config["shard_prefix"]
            self.shard_size = shatter_config["shard_size"]
        if branch is not None:
            self.out_dir = branch.get_shard_dir()
        if prefix is not None:
            self.prefix = prefix 
        if shard_size is not None:
            self.shard_size = shard_size 
        if out_dir is not None: 
            self.out_dir = Path(out_dir).expanduser().resolve() 

    @classmethod
    def from_path(cls, out_path: Path | str, prefix: str, size: int = 2024 ) -> "ShardRequest": 
        return cls(prefix=prefix, shard_size=size, out_dir=out_path)


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
        takes in ShardRequest and safely open, make sure path for tar is valid, 
        and for an EncodedTile write each of key.npy and key.json for that tiles bytes 
        Return a ShardPlacement object with pointer to shard and tile key. 

        Input 
        ---------- 
        request: ShardRequest(Mosaic_Branch, Config)
        
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
    request: ShardRequest 
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

@dataclass 
class SplitShardWriter: 
    """ 
        router for ShardWriter to direct encoded tiles into damage/nodamage subdirectories 

        input 
        ------ 
        takes a shard request with config, tokens and instantiates two new SplitShardRequests  
    """

    def __init__(self, request: ShardRequest): 
        self.dmg_dir = request.out_dir / "damage"
        self.ndmg_dir = request.out_dir / "nodamage"
        
        self.dmg_req = ShardRequest(prefix="damage", shard_size=2024, out_dir=self.dmg_dir)
        self.ndmg_req = ShardRequest(prefix="nodamage", shard_size=2024, out_dir=self.ndmg_dir)

        self.dmg_writer = ShardWriter(self.dmg_req)
        self.ndmg_writer = ShardWriter(self.ndmg_req)

    def __enter__(self) -> "SplitShardWriter":
        return self 

    def __exit__(self, exc_type, exc, tb) -> None: 
        self.close()

    def write(self, tile: EncodedTile) -> ShardPlacement:
        metadata = tile.metadata
        damage = metadata["labels"]["damage"]
        
        if damage: 
            return self.dmg_writer.write(tile)
        else: 
            return self.ndmg_writer.write(tile)

    def close(self) -> None:
        if self.dmg_writer.tar is not None:
            self.dmg_writer.close()

        if self.ndmg_writer.tar is not None:
            self.ndmg_writer.close()

