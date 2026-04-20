


"""
PROTOCOLS: 
class RasterShape(Protocol): 
        def width
        def height
        def count 

class ProtoRaster(RasterShape, Protocol)
        def dtypes
    
class GeoRaster(ProtoRaster, Protocol)
        def transform 
        def crs 
        def read 



class ProtoRaster(Protocol):
    @property
    def width(self) -> int: ...
    @property
    def height(self) -> int: ...
    @property
    def count(self) -> int: ...
    @property
    def dtypes(self) -> Sequence[str]: ...
    @property
    def transform(self) -> Any: ...
    @property
    def crs(self) -> Any: ...

    def read(
        self,
        indexes: int | Sequence[int] | None = None,
        window: object | None = None,
        out_dtype: str | np.dtype | None = None,
        masked: bool = False,
    ) -> np.ndarray: ...
    T
"""



def num_tiles_in_raster(ds: Raster,  tile_size: int, stride: int) -> int:
    tiles_x = max(1, (ds.width - tile_size) // stride + 1)
    tiles_y = max(1, (ds.height - tile_size) // stride + 1)
    return tiles_x * tiles_y

"""Raster.window_bounds(window: WindowLike)-> Bounds """

def window_bounds(ds: rasterio.DatasetReader, win: Window) -> tuple[float,float, float, float]:
    return rasterio.windows.bounds(win, ds.transform)

def iter_windows(ds: rasterio.DatasetReader, tp: TParams) -> Iterator[Tuple[int, int, Window]]:
    max_x = ds.width
    max_y = ds.height
    tile_size = tp.tile_size
    stride = tp.stride
    if tp.drop_partial:
        x_stops = range(0, max_x - tile_size + 1, stride)
        y_stops = range(0, max_y - tile_size + 1, stride)
    else:
        x_stops = range(0, max_x, stride)
        y_stops = range(0, max_y, stride)
    for ry, y in enumerate(y_stops):
        for cx, x in enumerate(x_stops):
            w = tile_size if (x + tile_size <= max_x) else (max_x - x)
            h = tile_size if (y + tile_size <= max_y) else (max_y - y)
            if tp.drop_partial and (w != tile_size or h != tile_size):
                continue
            yield ry, cx, Window(x, y, w, h) 



def _quant_dtype(dtype: str) -> np.dtype:
    d = dtype.lower()
    if d == "float32":
        return np.float32
    if d == "uint16":
        return np.uint16
    if d == "uint8":
        return np.uint8
    raise ValueError(f"unsupported dtype: {dtype}")


def _dst_range(dtype: str) -> Tuple[float, float]:
    d = dtype.lower()
    if d == "uint16":
        return 0.0, 65535.0
    if d == "uint8":
        return 0.0, 255.0
    if d == "float32":
        return 0.0, 1.0
    raise ValueError(f"unsupported dtype: {dtype}")


def sample_band(
    ds: rasterio.DatasetReader,
    tile_size: int,
    stride: int,
    qp: QuantizationParams,
    p: Progress()
) -> Dict[int, Tuple[float, float]]:
    if qp.scale == "none":
        return {}

    nb = ds.count
    lo_hi: Dict[int, List[float]] = {b: [] for b in range(1, nb + 1)}
    need = max(1, int(qp.num_samples))

    tiles_x = max(1, (ds.width - tile_size) // stride + 1)
    tiles_y = max(1, (ds.height - tile_size) // stride + 1)
    n_tiles = tiles_x * tiles_y

    step = max(1, int(math.sqrt(n_tiles / need)))
    sparse_total = math.ceil(tiles_y / step) * math.ceil(tiles_x / step)
    total = min(need, sparse_total)

    sampled = 0
    sample_task = p.add_task(description=f"sampling {nb} bands", total=min(need,sparse_total))
    for ty in range(0, tiles_y, step):
        y = ty * stride
        for tx in range(0, tiles_x, step):
            p.update(sample_task, advance=1)
            x = tx * stride
            win = Window(x, y, tile_size, tile_size)
            data = ds.read(window=win, out_dtype=np.float32, masked=True)

            for bi in range(nb):
                band = data[bi]
                if getattr(band, "mask", None) is not None and band.mask.all():
                    continue
                vals = band.compressed() if hasattr(band, "compressed") else band.ravel()
                if vals.size == 0:
                    continue

                if qp.scale == "minmax":
                    lo_hi[bi + 1].append(float(np.min(vals)))
                    lo_hi[bi + 1].append(float(np.max(vals)))
                elif qp.scale == "percentile":
                    lo = float(np.percentile(vals, qp.p_low))
                    hi = float(np.percentile(vals, qp.p_high))
                    lo_hi[bi + 1].append(lo)
                    lo_hi[bi + 1].append(hi)

            sampled += 1
            if sampled >= need:
                break
        if sampled >= need:
            break

    out: Dict[int, Tuple[float, float]] = {}
    for b in range(1, nb + 1):
        xs = lo_hi[b]
        out[b] = (0.0, 1.0) if not xs else (min(xs), max(xs))
    return out


def quantize_tile(
    arr: np.ndarray,
    qp: QuantizationParams,
    band_bounds: Dict[int, Tuple[float, float]],
) -> Tuple[np.ndarray, Dict[str, object]]:
    out_dtype = _quant_dtype(qp.dtype)

    if qp.scale == "none":
        if qp.dtype.lower() == "float32":
            return arr.astype(np.float32, copy=False), {"scale": "none", "dtype": "float32"}
        dst_lo, dst_hi = _dst_range(qp.dtype)
        clipped = np.clip(arr, dst_lo, dst_hi)
        return clipped.astype(out_dtype), {"scale": "none", "dtype": qp.dtype.lower(), "clipped_to": [dst_lo, dst_hi]}

    dst_lo, dst_hi = _dst_range(qp.dtype)
    nb = int(arr.shape[0])
    scaled = np.empty_like(arr, dtype=np.float32)

    meta: Dict[str, object] = {
        "scale": qp.scale,
        "dtype": qp.dtype.lower(),
        "per_band": True,
        "dst_range": [dst_lo, dst_hi],
        "bands": [],
    }

    for bi in range(nb):
        b = bi + 1
        src_lo, src_hi = band_bounds.get(b, (0.0, 1.0))
        if not np.isfinite(src_lo) or not np.isfinite(src_hi) or src_hi <= src_lo:
            src_lo, src_hi = 0.0, 1.0

        band = arr[bi]
        s = (band - src_lo) * (dst_hi - dst_lo) / (src_hi - src_lo) + dst_lo
        scaled[bi] = s
        meta["bands"].append({"band": b, "src_lo": float(src_lo), "src_hi": float(src_hi)})

    scaled = np.clip(scaled, dst_lo, dst_hi)

    if qp.dtype.lower() == "float32":
        return scaled.astype(np.float32, copy=False), meta

    return scaled.astype(out_dtype), meta


def mosaic_dirs(out_root: Path, mosaic_id: str) -> Tuple[Path, Path]:
    shards_dir = out_root / str(mosaic_id) / "shards"
    manifest_dir = out_root / str(mosaic_id) / "manifest"
    shards_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)
    return shards_dir, manifest_dir

@dataclass(frozen=True)
class TParams:

    uris: list[str]
    out_dir: Path
    tile_size: int
    stride: int
    drop_partial: bool
    shard_size: int
    shard_prefix: str
    manifest_kind: str

    def validate(self) -> None:
        if self.tile_size <= 0:
            face.error("param init error: tile_size must be > 0")
        if self.stride <= 0:
            face.error("param init error: stride must be > 0")
        if self.shard_size <= 0:
            face.error("param init error: shard_size must be > 0")
    def print_table(self) -> None:
        cols = ["tiling params","value"]
        rows = [
                ["uris",len(self.uris)],
                ["destination",str(self.out_dir)],
                ["tile size",self.tile_size],
                ["stride",self.stride],
                ["drop partials", self.drop_partial],
                ["shard size", self.shard_size],
                ["manifest", self.manifest_kind]
                ]
        face.table(cols,rows)

@dataclass(frozen=True)
class QParams:
    dtype: str
    scale: str
    p_low: float
    p_high: float
    per_band: bool
    stats: str
    num_samples: int
    

    def validate(self) -> None:
        if self.scale == "percentile":
            if not (0.0 <= self.p_low < self.p_high <= 100.0):
                face.error("param init error: percentile scaling requires 0 <= p_low <p_high <= 100")
        if self.num_samples <= 0:
                face.error("param init error: num_samples must be > 0")
    def print_table(self) -> None:
        cols = ["quant params", "value"]
        rows = [ 
                ["dtype",self.dtype],
                ["scaling", self.scale],
                ["low", self.p_low],
                ["high", self.p_high],
                ["per band", self.per_band],
                ["stats", self.stats],
                ["sampling", self.num_samples]
                ]

        face.table(cols,rows)

@dataclass(frozen=True)
class Tile:
    tile_id: str
    mosaic_id: str
    source_uri: str
    row_id: int
    col_id: int
    transform: Affine
    window: Window
    crs: str | None

    @property
    def width(self) -> int:
        return int(self.window.width)

    @property
    def height(self) -> int:
        return int(self.window.height)


def tesselate(
    tile: Tile,
    ds: rasterio.DatasetReader,
    qp: QParams,
    tp: TParams,
    band_bounds: Dict[int, Tuple[float, float]],
    ) -> Tuple[bytes, bytes, Dict[str, Any]]:

    arr = ds.read(window=tile.window, masked=True, out_dtype=np.float32)
    if np.ma.isMaskedArray(arr):
        arr = np.ma.filled(arr, 0.0).astype(np.float32, copy=False)
    else:
        arr = arr.astype(np.float32, copy=False)

    out_arr, q_meta = quantize_tile(arr, qp, band_bounds)

    t_transform = rasterio.windows.transform(tile.window, ds.transform)
    minx, miny, maxx, maxy = window_bounds(ds, tile.window)

    meta: Dict[str, Any] = {
        "tile_id": tile.tile_id,
        "source_uri": tile.source_uri,
        "mosaic_id": tile.mosaic_id,
        "tile_size": tile.height,
        "stride": tp.stride,
        "window": {
            "x_off": int(tile.window.col_off),
            "y_off": int(tile.window.row_off),
            "w": int(tile.width),
            "h": int(tile.height),
        },
        "crs": tile.crs,
        "transform": dm.affine_to_list(t_transform),
        "bounds": {"minx": float(minx), "miny": float(miny), "maxx": float(maxx), "maxy": float(maxy)},
        "bands": int(ds.count),
        "dtype": str(out_arr.dtype),
    }
    if q_meta:
        meta["scaling"] = q_meta

    try:
        if ds.crs:
            wgs84 = transform_bounds(ds.crs, "EPSG:4326", minx, miny, maxx, maxy, densify_pts=0)
            meta["bounds_wgs84"] = {
                "minx": float(wgs84[0]),
                "miny": float(wgs84[1]),
                "maxx": float(wgs84[2]),
                "maxy": float(wgs84[3]),
            }
        else:
            meta["bounds_wgs84"] = {"minx": 0.0, "miny": 0.0, "maxx": 0.0, "maxy": 0.0}
    except Exception:
        meta["bounds_wgs84"] = {"minx": 0.0, "miny": 0.0, "maxx": 0.0, "maxy": 0.0}

    return dm.npy_bytes(out_arr), dm.json_bytes(meta), meta

@dataclass
class IngestMosaicsRunner: 
    tp: TParams 
    qp: QParams 

    @classmethod 
    def from_config(  
                    cls, 
                    input_source: str, 
                    config: Dict[str, Any],
                    ) -> "IngestMosaicsRunner":
        tp, qp = build_params(input_source, config)
        return cls(tp=tp,qp=qp,log=base.child("mosaics"))

    def run(self) -> Tuple[Any, Any]:
        """ run ingest for all uris, returns per mosaic summary """
        
        if not self.tp or not self.qp:
            return ("error",3) 
        self.tp.print_table()
        self.qp.print_table()

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



def cut_mosaic(
               
               uri: str,
               man_dir: Path,
               shard_dir: Path, 
               qp: QParams, 
               tp: TParams, 
               ) -> tuple[str,int,int,int,int,float]:
    n_seen = 0 
    n_skipped = 0 
    n_errors = 0 
    n_written = 0 
    
    if not Path(uri).exists:
        face.error(f"path error: {uri} not a valid source path for ingest")

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
            band_bounds: Dict[int, Tuple[float, float]] = {}

            if qp.scale != "none":
                
                ########################################################
                # SAMPLE BANDS ---> QUANTIZE 
                band_bounds = sample_band(ds, tile_size, stride, qp, p) 
                # ######################################################

            #######################
            # ITERWINDOWS 
            #######################
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

                        # TESSELATE###############################################
                        npy, js, meta = tesselate( tile, ds, qp, tp, band_bounds)
                        ##########################################################


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
