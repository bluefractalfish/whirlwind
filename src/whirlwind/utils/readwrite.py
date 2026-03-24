from whirlwind.imps import *
from . import pathfinder as pf
from . import geographer as geo
from ..ui.tui import TUI 

ui = TUI()

@dataclass
class ShardWriter:
    out_dir: Path
    prefix: str
    shard_size: int 
    shard_index: int=1
    samples_in_shard: int = 0
    tar: Optional[tarfile.Tarfile] = None
    tar_path: Optional[Path] = None 

    def _open_next(self) -> None:
        """
        if shard is empty, create new/next shard
        """
        if self.tar is not None:
            self.tar.close()
        name = f"{self.prefix}-{self.shard_index:03d}.tar"
        self.tar_path = self.out_dir/name
        self.tar = tarfile.open(self.tar_path, "w")
        self.samples_in_shard = 0
        self.shard_index += 1
    def _write_sample(self, key: str, npy: bytes, meta_json: bytes):
        """
        write <key>.npy and <key>.json into current tar
        returns: (shard_filename, key)
        """
        # for new shard depending on mosaic size, change here
        if self.tar is None or self.samples_in_shard >= self.shard_size:
            self._open_next()
        assert self.tar is not None
        assert self.tar_path is not None

        npy_name = f"<{key}>.npy"
        ti = tarfile.TarInfo(npy_name)
        ti.size = len(npy)
        ti.mtime = int(time.time())
        self.tar.addfile(ti, io.BytesIO(npy))

        js_name = f"<{key}>.json"
        tj = tarfile.TarInfo(js_name)
        tj.size = len(meta_json)
        tj.mtime = int(time.time())
        self.tar.addfile(tj, io.BytesIO(meta_json))

        self.samples_in_shard += 1
    def _close(self) -> None:
        # only close non Null tars
        if self.tar is not None:
            self.tar.close()
            self.tar = None
@dataclass 
class ManifestRow:
    tile_id: str
    shard: str
    key: str
    source_uri: str 
    x_off: int   
    y_off: int
    w: int
    h: int
    crs: str
    minx: float
    miny: float
    maxx: float
    maxy: float
    bands: int
    dtype: str

class ManifestSink:
    def _write(self, row: ManifestRow) -> None:
        raise NotImplementedError
    def _close(self) -> None:
        raise NotImplementedError

class CSVSink(ManifestSink):
    def __init__(self, path: Path):
        self.path = path
        pf._mkdir_(path.parent)
        self.f = open(path, "w", newline="",encoding="utf-8")
        self.w = csv.DictWriter(
            self.f,
            fieldnames=[
                "tile_id", "shard", "key", "source_uri", "x_off", "y_off", "w", "h", "crs",
                "minx", "miny", "maxx", "maxy", "bands", "dtype",
            ],
        )
        self.w.writeheader()
    def _write(self, row: ManifestRow) -> None:
        self.w.writerow(row.__dict__)
    def _close(self) -> None:
        self.f.close()

@dataclass
class Parquet(ManifestSink):
    def __init__(self, path: Path):
        self.path = path
        pf._mkdir_(path.parent)
        self.rows: List[dict] =[]
        try:
            import pyarrow as pa 
            import pyarrow.parquet as pq 
        except Exception as e:
                raise RuntimeError(f"pyarrow required for parquet manifest: {e}")
        self.pa = pa 
        self.pq = pq

    def _write(self, row: ManifestRow) -> None:
        record = {}
        for key, value in row.__dict__.items():
            if isinstance(value,Path):
                record[key] = str(value)
            else:
                record[key] = value
        self.rows.append(record)

    def _close(self) -> None:
        table = self.pa.Table.from_pylist(self.rows)
        self.pq.write_table(table, str(self.path))
def make_sink(kind: str, path: Path) -> ManifestSink:
    k = kind.lower()
    if k == "csv":
        return CSVSink(path)
    if k == "parquet":
        return Parquet(path)
    if k == "none":
        class  _Null(ManifestSink):
            def _write(self, row: ManifestRow) -> None:
                return
            def _close(self) -> None:
                return 
        return _Null()
    raise ValueError(f"unknown manifest kind: {kind}")
def write_metadata(input_dir: str, out_csv: str, columns: Optional[List[str]] = None) -> None:
    """
    Walk `input_dir` consisting of mosaics, extract metadata for each tif/tiff, write CSV to `out_csv`.

    If `columns` is None, a default mosaic_stage-compatible column list is used.
    """
    input_path = Path(input_dir)
    output_path = Path(pf._find_home_()/"metadata"/out_csv)
    rows: List[Dict[str, Any]] = []

    if columns is None:
        columns = [
            "mosaic_id",
            "uri",
            "uri_etag",
            "byte_size",
            "crs",
            "srid",
            "pixel_width",
            "pixel_height",
            "band_count",
            "dtype",
            "nodata",
            "footprint",
            "acquired_at",
            "created_at"
        ]

    for tif in _search_ext_(input_path):
        rows.append(geo.extract_metadata(str(tif), columns))
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        for r in rows:
            # Ensure all requested columns exist; fill missing with ""
            w.writerow({k: r.get(k, "") for k in columns})

def _search_ext_(root: Path, extensions=(".tif", ".tiff")) -> Iterable[Path]:
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in extensions:
            yield p

def _iter_uris(source: str, extensions: tuple[str,...]=(".tif",".tiff")) -> Iterator[str]:
    """
    yield geotiff uris from either:
        - a metadata csv with uri column (see write/extract_metadata)
        - a directory
        - a glob
    """
    if not source: 
        raise ValueError("input source is required for _iter_uris")
    s = source.strip()
    p = Path(s).expanduser()
    ui.row("input",p)
    # check if csv
    if p.is_file() and p.suffix.lower() == ".csv":
        ui.print("(input path is a file)")
        with open(source, newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            if "uri" not in (r.fieldnames or []):
                raise ValueError(f"input CSV missing uri column: {source}")
            for row in r:
                uri = (row.get("uri") or "").strip()
                if uri:
                    yield uri
        return
    # check if directory
    if p.is_dir():
        n_files = sum(1 for f in p.rglob("*") if f.is_file())
        ui.print("(input path is a directory)")
        with ui.progress() as pr: 
            task = pr.add_task(f"recursing {p}", total=n_files)
            for tif in p.rglob("*"):
                pr.update(task,advance=1)
                if tif.is_file() and tif.suffix.lower() in extensions:
                    yield str(tif)
        return

    # Otherwise treat as glob
    matches = False
    for tif in Path().glob(s):
        if tif.is_file() and tif.suffix.lower() in extensions:
            matches = True
            yield str(tif)
    if matches:
        return
    raise ValueError(f"could not resolve input as csv, directory, or glob: {source}")


