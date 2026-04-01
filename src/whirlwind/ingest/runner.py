"""whirlwind.ingest.runner 

    PURPOSE:
        - orchestrates multimosaic tiling logic 

    BEHAVIOR:
        - for each input mosaic (uri):
            - open dataset (rasterio)
            
            - sample band bounds if given 
            - iterate windows deterministaclly 
            - cut tile payload 
            - write into shard tars 
            - write manifest rows 
        - provide experiment/performance metrics if requested 
    PUBLIC:
        - IngestMosaicsRunner
            - from_config(config)
            - experimental()
        - tesselate(tokwns, config, log) -> int 
"""

from __future__ import annotations 
 
import time 
from dataclasses import dataclass 
from pathlib import Path 
from typing import Any, Dict, List, Tuple 

import numpy as np 
import rasterio 
from rasterio.windows import Window 

from whirlwind.core.interfaces import LoggerProtocol, NullLogger
from whirlwind.geo.windows import iter_windows, num_tiles

from whirlwind.ingest.config import build_params
from whirlwind.ingest.tesselater import Tile, tesselate
from whirlwind.ingest.params import QParams, TParams
from whirlwind.ingest.planner import mosaic_dirs
from whirlwind.ingest.quantize import sample_band

from whirlwind.io.manifests import ManifestRow, make_sink
from whirlwind.io.shards import ShardWriter

from whirlwind.tools import datamonkeys as dm
from whirlwind.tools import ids
from whirlwind.tools.timer import StopWatch

from whirlwind.ui import face
from rich.traceback import install 

install(show_locals=True)

@dataclass
class IngestMosaicsRunner: 
    tp: TParams 
    qp: QParams 
    log: LoggerProtocol 

    @classmethod 
    def from_config(  
                    cls, 
                    input_source: str, 
                    config: Dict[str, Any],
                    log: LoggerProtocol | None=None, ) -> "IngestMosaicsRunner":
        base = log or NullLogger()
        tp, qp = build_params(input_source, config)
        return cls(tp=tp,qp=qp,log=base.child("mosaics"))

    def run(self) -> Tuple[Any, Any]:
        """ run ingest for all uris, returns per mosaic summary """

        # per mosaic summary 
        summary: List[Dict[str, Any]] = []
        
        # for total run performance specs 
        started = time.perf_counter()
        ids_seen: List[str] = [] 
        total_seen = 0 
        total_written = 0 
        total_errors = 0 
        total_skipped = 0 
        tile_times: list[float] = [] 

        for uri in self.tp.uris: 
            u = uri.strip()
            if not u:
                continue 

            mosaic_id = ids.gen_uuid_from_str(u) 
            shards_dir, manifest_dir = mosaic_dirs(self.tp.out_dir, mosaic_id)

            mid, seen, written, errors, skipped, avg_tile_time = cut_mosaic(
                    u, manifest_dir, shards_dir, self.qp, self.tp, log=self.log)

            total_seen += seen 
            total_written += written 
            total_errors += errors 
            total_skipped += skipped 
            if avg_tile_time > 0:
                tile_times.append(avg_tile_time) 
            ids_seen.append(mosaic_id)
                

            summary.append(
                    {   
                        "manifest": str(manifest_dir),
                        "shards": str(shards_dir), 
                        "mosaic_id": mid, 
                        "seen": seen, 
                        "errors": errors
                     }
                    )
        total_seconds = time.perf_counter() - started 
        shard_count, shard_bytes = dm.count_bytes(self.tp.out_dir, ".tar")
        manifest_count_csv, manifest_bytes_csv = dm.count_bytes(self.tp.out_dir, "csv")
        manifest_count_parquet, manifest_bytes_parquet = dm.count_bytes(self.tp.out_dir, "parquet")

        manifest_count = manifest_count_csv + manifest_count_parquet
        manifest_bytes = manifest_bytes_csv + manifest_bytes_parquet 
        out_bytes = dm.dir_bytes(self.tp.out_dir) 

        overview =  { 
                "uids": ids_seen, 
                "input_uri_count": len(self.tp.uris), 
                "tile_size": self.tp.tile_size, 
                "stride": self.tp.stride, 
                "drop_partial": self.tp.drop_partial, 
                "shard_size": self.tp.shard_size, 
                "manifest_kind": self.tp.manifest_kind, 
                "dtype": self.qp.dtype, "scale": self.qp.scale,
                "p_low": self.qp.p_low,
                "p_high": self.qp.p_high,
                "per_band": self.qp.per_band,
                "stats": self.qp.stats,
                "num_samples": self.qp.num_samples,
                "total_seen": total_seen,
                "total_written": total_written,
                "total_errors": total_errors,
                "total_skipped": total_skipped,
                "shard_count": shard_count,
                "shard_bytes": shard_bytes,
                "manifest_count": manifest_count,
                "manifest_bytes": manifest_bytes,
                "out_bytes": out_bytes,
                "avg_tile_seconds": float(np.mean(tile_times)) if tile_times else 0.0,
                "total_seconds": total_seconds,
                }

        return summary, overview  



def cut_mosaic(uri: str,
               man_dir: Path,
               shard_dir: Path, 
               qp: QParams, 
               tp: TParams, 
               log: LoggerProtocol | None=None 
               ) -> tuple[str,int,int,int,int,float]:
    n_seen = 0 
    n_skipped = 0 
    n_errors = 0 
    n_written = 0 
    mosaic_id = ids.gen_uuid_from_str(uri)
    writer = ShardWriter(
            out_dir=shard_dir,prefix=mosaic_id,shard_size=tp.shard_size)
    k = tp.manifest_kind.lower()
    mosaic_man_path = man_dir/(f"{mosaic_id}.parquet" if k == "parquet" else f"{mosaic_id}.csv")

    fieldnames =[ "tile_id", "shard", "key", "source_uri", "x_off", "y_off", "w", "h", "crs",
                "minx", "miny", "maxx", "maxy", "bands", "dtype",]

    sink = make_sink(k,mosaic_man_path,fieldnames)
    time_per_tile = []
    try:
        with rasterio.open(uri) as ds:
            tile_size = tp.tile_size
            stride = tp.stride
            total_tiles = num_tiles(ds, tile_size, stride) 
            band_bounds: Dict[int, Tuple[float, float]] = {}
            with face.progress() as p:
                if qp.scale != "none":
                    band_bounds = sample_band(ds, tile_size, stride, qp, p) 

                t = p.add_task(description=f"tiling {mosaic_id}",total=total_tiles)
                for r_i, c_i, win in iter_windows(ds,tp):
                    p.update(t, advance=1)
                    # one tile per iteration
                    n_seen += 1
                    try:
                        with StopWatch() as sw: 
                            tid = ids.gen_tile_id(mosaic_id, r_i, c_i)
                            #cut_tile returns Tile object
                            tile = Tile(
                                    tile_id = tid,
                                    mosaic_id = mosaic_id,
                                    source_uri = uri,
                                    row_id = r_i,
                                    col_id = c_i,
                                    window = win,
                                    transform = ds.transform,
                                    crs=ds.crs.to_string() if ds.crs else None,
                                    )
                            npy, js, meta = tesselate( tile, ds, qp, tp, band_bounds)
                            writer.write_sample(tid,npy,js)
                            bounds = meta.get("bounds_wgs84") or {"minx": 0.0, "miny": 0.0, 
                                                                  "maxx": 0.0, "maxy": 0.0 }

                            manifest_row = ManifestRow(
                                tile_id=tid,
                                shard=str(writer.tar_path) if writer.tar_path is not None else "",
                                key=tid,
                                source_uri=uri,
                                x_off=int(win.col_off),
                                y_off=int(win.row_off),
                                w=int(win.width),
                                h=int(win.height),
                                crs=tile.crs,
                                minx=float(bounds["minx"]),
                                miny=float(bounds["miny"]),
                                maxx=float(bounds["maxx"]),
                                maxy=float(bounds["maxy"]),
                                bands=int(ds.count),
                                dtype=str(meta.get("dtype") or ""),
                                )

                            sink.write(manifest_row)
                            n_written += 1 
                        if sw.elapsed is not None:
                            time_per_tile.append(sw.elapsed)
                    except KeyboardInterrupt:
                        writer.close()
                        sink.close()
                        raise
                    except Exception as e:
                        n_errors += 1
                        continue
    except KeyboardInterrupt:
        writer.close()
        sink.close()
        raise
    except Exception as e:
        n_errors += 1
        raise e

    finally:
        writer.close()
        sink.close()
    average_time_per_tile = float(np.mean(time_per_tile)) if time_per_tile else 0.0
    return mosaic_id, n_seen, n_written, n_errors, n_skipped, average_time_per_tile
