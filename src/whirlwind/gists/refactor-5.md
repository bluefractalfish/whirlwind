# Whirlwind Refactored Branch: Mosaic ID, Selection, RunTree, and Metamosaic Refactor Plan


---

## 0. Current Branch Baseline

### 0.1 Entrypoint and command flow

Current shell startup:

```text
pyproject.toml
  W = "whirlwind.cli:main"

src/whirlwind/cli.py
  parse --config
  Config(config_doc)
  bootstrapp(config)

src/whirlwind/entrypoint/__init__.py
  init_gdal()
  app = WhirlwindApp(cmds=[Test()], config=config)
  WShell(app).run()

src/whirlwind/entrypoint/shell.py
  cmd2 shell
  shlex.split(line)
  app.run(tokens)

src/whirlwind/entrypoint/app.py
  head = tokens[0]
  command = self._commands.get(head)
  command.run(tokens[1:], config)
```

The current architecture is already command-shell driven, not argparse-subcommand driven.

### 0.2 Bridge pattern

`src/whirlwind/commands/bridge.py` already defines the correct architectural seam:

```text
tokens + config
  -> RequestBuilder
  -> BridgeRequest
  -> Bridge.run()
  -> BridgeResult
  -> ResultReporter
  -> exit code
```

This means the refactor should preserve the bridge pattern and improve the objects passed through it.

### 0.3 Current command router

`src/whirlwind/commands/test.py` currently routes:

```text
test ids         -> WriteIDManifestCommand
test meta        -> DiscoverMetadataCommand
test tileplan    -> StageTesselationCommand
test tile        -> TesselationCommand
test downsample  -> DownsampleCommand
test pathplan    -> StagePathsCommand
test export      -> ExportShardsCommand
```

This is acceptable during refactor, but later these should become real top-level registered commands instead of being hidden under `test`.

### 0.4 Current RunTree shape

`src/whirlwind/domain/filesystem/runtree.py` currently holds:

```python
RunTree(
    root: Path,
    manifest_dir: Path,
)
```

and plants branches with:

```python
RunTree.plant_mosaic_branch(file_id)
  -> MosaicBranch.plant(self.root, file_id)
```

### 0.5 Current MosaicBranch shape

`src/whirlwind/domain/filesystem/mosaicbranch.py` currently hardcodes:

```text
root/
  file_id/
    browse/
    shards/
    tiles/
    manifest/
    metadata/
    staging/
```

through:

```python
mosaic_dir = root / file_id
```

### 0.6 Current RasterFile / FileID issue

`src/whirlwind/domain/filesystem/files.py` currently has:

```python
RasterFile.file_id
RasterFile.mosaic_id
RasterFile.mid
```

all returning the same `raster_id`.

Current `raster_file_id()` hashes the parent directory:

```python
h = short_hash(p.parent.as_uri(), size=4)
return f"m{h}{variant.variant_id}"
```

This makes mosaic naming hard to change safely and risks collisions between multiple rasters of the same variant in the same directory.

### 0.7 Current manifest issue

`src/whirlwind/adapters/io/idmanifest.py` writes records from `RasterFile.record()`.

But there is a schema mismatch:

```python
RasterFile.record()
  -> "file_id"

IDManifest.ids()
  -> reads "id"

IDManifest.mids()
  -> reads "mids"
```

The manifest is not yet a stable mosaic catalog.

### 0.8 Current operation coupling

These bridges/builders currently depend on raw paths and direct branch construction:

```text
commands/builders/downsample_cmd.py
bridges/rasterops/downsample.py

commands/builders/stage_tesselation_cmd.py
bridges/staging/stage_tesselation.py

commands/builders/tesselate_mosaics_cmd.py
bridges/rasterops/tesselate.py

commands/builders/stage_damagepaths_cmd.py
bridges/staging/stage_damagepaths.py

commands/builders/export_shards_cmd.py
bridges/tiling/shards_to_tifs.py

commands/builders/discover_metadata_cmd.py
bridges/catalogs/discovermetadata.py
```

Common current pattern:

```python
manifest = IDManifest(manifest_path)
paths = manifest.paths()

for p in paths:
    f = RasterFile(p)
    fid = f.file_id
    branch = MosaicBranch.plant(request.tree.root, fid)
```

This is the main pattern to remove.

---

# 1. Target Architecture

## 1.1 Target dependency flow

```text
Command / shell tokens
  -> TokenView
  -> MosaicSelector
  -> MosaicCatalog
  -> MosaicRecord(s)
  -> Bridge Request
  -> Bridge
  -> RunTree
  -> MosaicBranch / MetamosaicTree
  -> IO adapters
```

## 1.2 Do not allow this dependency flow

```text
Bridge
  -> raw Path
  -> RasterFile(path)
  -> file_id string
  -> MosaicBranch.plant(tree.root, file_id)
```

That form couples every operation to the current ID scheme and current directory layout.

## 1.3 New stable concepts

Add these concepts:

```text
FileID
  Owns all ID generation.

MosaicRecord
  Stable row object for one source mosaic.

MosaicSelector
  Represents user selection of one or more mosaics.

MosaicCatalog
  Reads IDManifest / root manifest and yields MosaicRecord objects.

RunTreeLayout
  Owns directory layout policy.

RunTree
  Uses RunTreeLayout to resolve branch and metamosaic paths.

MetamosaicTree
  Filesystem object for one overlap-connected mosaic group.

RunManifest
  Root-level manifest describing current branch/metamosaic organization.
```

---

# 2. Phase 1 — Isolate All ID Logic

## Goal

Make it possible to completely change how mosaics are named by editing one place only.

## Files to change

```text
src/whirlwind/domain/filesystem/files.py
src/whirlwind/domain/geometry/tiles/tile.py
src/whirlwind/adapters/io/idmanifest.py
```

## 2.1 Change `FileID`

Current `FileID` is a generic UID wrapper. Make it the public ID authority.

Add:

```python
class FileID:
    ID_SCHEME = "whirlwind-readable-v1"
    ID_VERSION = "1"

    @staticmethod
    def short_hash(value: str, size: int = 6) -> str:
        ...

    @staticmethod
    def mosaic(path: str | Path) -> str:
        ...

    @staticmethod
    def metamosaic(member_ids: tuple[str, ...], stem: str = "mm") -> str:
        ...

    @staticmethod
    def branch(mosaic_id: str) -> str:
        return mosaic_id

    @staticmethod
    def tile(mosaic_id: str, row_i: int, col_i: int) -> str:
        ...

    @staticmethod
    def shard(branch_id: str, shard_index: int) -> str:
        ...
```

Recommended mosaic ID shape:

```text
m-<date>-<variant>-<hash>
```

Example:

```text
m-240119-DSM-a31f
```

Recommended metamosaic ID shape:

```text
mm-<stem>-<hash>
```

Example:

```text
mm-denver-a9f031
```

## 2.2 Change `raster_file_id()`

Either remove it or turn it into a wrapper:

```python
def raster_file_id(path: str | Path, date: bool = False) -> str:
    return FileID.mosaic(path)
```

Do not keep separate logic in `raster_file_id()`.

## 2.3 Change `RasterFile.__init__`

Current:

```python
self.raster_id = raster_file_id(self.path)
```

Target:

```python
self.raster_id = FileID.mosaic(self.path)
```

## 2.4 Change `RasterFile.record()`

Current record fields:

```text
file_id
date
variant_id
variant_type
spectral_id
uri
path
```

Target record fields:

```text
mosaic_id
file_id              # temporary compatibility alias only
source_uri
uri                  # temporary compatibility alias only
path
date
variant_id
variant_type
spectral_id
id_scheme
id_version
```

Use `str(self.path)`, not `Path`, in records.

Target shape:

```python
return {
    "mosaic_id": self.mosaic_id,
    "file_id": self.mosaic_id,          # compatibility
    "source_uri": self.uri,
    "uri": self.uri,                    # compatibility
    "path": str(self.path),
    "date": date,
    "variant_id": variant.variant_id,
    "variant_type": variant.variant_type,
    "spectral_id": variant.spectral_id or "",
    "id_scheme": FileID.ID_SCHEME,
    "id_version": FileID.ID_VERSION,
}
```

## 2.5 Change `TileEncoder`

File:

```text
src/whirlwind/domain/geometry/tiles/tile.py
```

Current:

```python
def gen_tile_id(self, tile: Tile) -> str:
    row = tile.plan
    return f"{self.file_id}_r{row.row_i:03d}_c{row.col_i:03d}"
```

Target:

```python
def gen_tile_id(self, tile: Tile) -> str:
    row = tile.plan
    return FileID.tile(self.file_id, row.row_i, row.col_i)
```

Also add mosaic hierarchy metadata in `TileEncoder.to_metadata()`:

```text
mosaic_id
branch_id
metamosaic_id   # optional
```

Initially `metamosaic_id` can be absent until the MosaicRecord plumbing exists.

---

# 3. Phase 2 — Standardize Manifest and Add MosaicRecord

## Goal

Make the manifest a stable mosaic catalog, not just a CSV of paths.

## Files to change

```text
src/whirlwind/adapters/io/idmanifest.py
src/whirlwind/domain/filesystem/files.py
```

## New files to add

```text
src/whirlwind/domain/catalogs/__init__.py
src/whirlwind/domain/catalogs/mosaicrecord.py
src/whirlwind/adapters/io/mosaiccatalog.py
```

## 3.1 Add `MosaicRecord`

File:

```text
src/whirlwind/domain/catalogs/mosaicrecord.py
```

Shape:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class MosaicRecord:
    mosaic_id: str
    path: Path
    source_uri: str
    date: str
    variant_id: str
    variant_type: str = ""
    spectral_id: str = ""
    branch_id: str | None = None
    metamosaic_id: str | None = None
    id_scheme: str = ""
    id_version: str = ""

    @classmethod
    def from_row(cls, row: dict[str, str]) -> "MosaicRecord":
        mosaic_id = row.get("mosaic_id") or row.get("file_id") or row.get("id")
        if not mosaic_id:
            raise ValueError(f"manifest row missing mosaic id: {row}")

        path_raw = row.get("path") or ""
        if not path_raw:
            raise ValueError(f"manifest row missing path: {row}")

        return cls(
            mosaic_id=mosaic_id,
            path=Path(path_raw),
            source_uri=row.get("source_uri") or row.get("uri") or "",
            date=row.get("date") or "",
            variant_id=row.get("variant_id") or "",
            variant_type=row.get("variant_type") or "",
            spectral_id=row.get("spectral_id") or "",
            branch_id=row.get("branch_id") or None,
            metamosaic_id=row.get("metamosaic_id") or None,
            id_scheme=row.get("id_scheme") or "",
            id_version=row.get("id_version") or "",
        )
```

## 3.2 Add `IDManifest.rows()`

File:

```text
src/whirlwind/adapters/io/idmanifest.py
```

Add:

```python
def rows(self) -> Iterator[dict[str, str]]:
    with self.path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield dict(row)
```

## 3.3 Add `IDManifest.records()`

```python
def records(self) -> Iterator[MosaicRecord]:
    for row in self.rows():
        yield MosaicRecord.from_row(row)
```

## 3.4 Fix ID column readers

Current:

```python
def ids(self) -> Iterator[str]:
    yield from self._column("id")

def mids(self) -> Iterator[str]:
    yield from self._column("mids")
```

Target:

```python
def mosaic_ids(self) -> Iterator[str]:
    try:
        yield from self._column("mosaic_id")
    except ValueError:
        yield from self._column("file_id")

def ids(self) -> Iterator[str]:
    yield from self.mosaic_ids()

def mids(self) -> Iterator[str]:
    yield from self.mosaic_ids()
```

This gives compatibility without keeping bad schema names as first-class concepts.

## 3.5 Add `MosaicCatalog`

File:

```text
src/whirlwind/adapters/io/mosaiccatalog.py
```

Shape:

```python
from dataclasses import dataclass
from typing import Iterator

from whirlwind.adapters.io.idmanifest import IDManifest
from whirlwind.domain.catalogs.mosaicrecord import MosaicRecord
from whirlwind.domain.catalogs.mosaicselector import MosaicSelector

@dataclass(frozen=True)
class MosaicCatalog:
    manifest: IDManifest

    def records(self) -> Iterator[MosaicRecord]:
        yield from self.manifest.records()

    def select(self, selector: MosaicSelector) -> Iterator[MosaicRecord]:
        for record in self.records():
            if selector.matches(record):
                yield record
```

---

# 4. Phase 3 — Add Mosaic Selection

## Goal

Make every operation runnable on:

```text
all mosaics
one mosaic
a set of mosaic IDs
a variant
a date
a metamosaic
```

## Files to change

```text
src/whirlwind/commands/bridge.py
src/whirlwind/commands/builders/downsample_cmd.py
src/whirlwind/commands/builders/stage_tesselation_cmd.py
src/whirlwind/commands/builders/tesselate_mosaics_cmd.py
src/whirlwind/commands/builders/stage_damagepaths_cmd.py
src/whirlwind/commands/builders/export_shards_cmd.py
```

## New files to add

```text
src/whirlwind/domain/catalogs/mosaicselector.py
src/whirlwind/commands/selectors.py
```

## 4.1 Extend `TokenView`

Current `TokenView` only separates flags and args.

Add support for key-value options:

```text
--mosaic=m-240119-DSM-a31f
--variant=DSM
--date=240119
--metamosaic=mm-denver-a9f031
--limit=10
```

Target:

```python
@dataclass(frozen=True)
class TokenView:
    flags: set[str]
    args: list[str]
    options: dict[str, list[str]]

    @classmethod
    def parse(cls, tokens: list[str]) -> "TokenView":
        flags: set[str] = set()
        args: list[str] = []
        options: dict[str, list[str]] = {}

        for token in tokens:
            if token.startswith("--") and "=" in token:
                key, value = token.split("=", 1)
                options.setdefault(key, []).append(value)
            elif token.startswith("-"):
                flags.add(token)
            else:
                args.append(token)

        return cls(flags=flags, args=args, options=options)

    def values(self, *names: str) -> tuple[str, ...]:
        out: list[str] = []
        for name in names:
            out.extend(self.options.get(name, []))
        return tuple(out)
```

## 4.2 Add `MosaicSelector`

File:

```text
src/whirlwind/domain/catalogs/mosaicselector.py
```

Shape:

```python
from dataclasses import dataclass
from whirlwind.domain.catalogs.mosaicrecord import MosaicRecord

@dataclass(frozen=True)
class MosaicSelector:
    mosaic_ids: tuple[str, ...] = ()
    variants: tuple[str, ...] = ()
    dates: tuple[str, ...] = ()
    metamosaic_ids: tuple[str, ...] = ()
    limit: int | None = None

    def matches(self, record: MosaicRecord) -> bool:
        if self.mosaic_ids and record.mosaic_id not in self.mosaic_ids:
            return False
        if self.variants and record.variant_id not in self.variants:
            return False
        if self.dates and record.date not in self.dates:
            return False
        if self.metamosaic_ids and record.metamosaic_id not in self.metamosaic_ids:
            return False
        return True
```

## 4.3 Add selector builder

File:

```text
src/whirlwind/commands/selectors.py
```

Shape:

```python
from whirlwind.commands.bridge import TokenView
from whirlwind.domain.catalogs.mosaicselector import MosaicSelector

def selector_from_tokens(tv: TokenView) -> MosaicSelector:
    limit_values = tv.values("--limit")
    limit = int(limit_values[-1]) if limit_values else None

    return MosaicSelector(
        mosaic_ids=tv.values("--mosaic", "--mosaic-id"),
        variants=tv.values("--variant"),
        dates=tv.values("--date"),
        metamosaic_ids=tv.values("--metamosaic", "--metamosaic-id"),
        limit=limit,
    )
```

## 4.4 Command syntax after this phase

Examples:

```text
test tileplan --mosaic=m-240119-DSM-a31f
test tileplan --variant=DSM
test downsample --date=240119
test pathplan --mosaic=m-240119-RGB-b7c2
test tile --metamosaic=mm-denver-a9f031
test export --variant=RGB --damage
```

---

# 5. Phase 4 — Make RunTree Layout-Driven

## Goal

Make future directory reorganization possible without breaking commands or bridges.

## Files to change

```text
src/whirlwind/domain/filesystem/runtree.py
src/whirlwind/domain/filesystem/mosaicbranch.py
src/whirlwind/commands/context.py
src/whirlwind/domain/config/defaults.py
```

## New files to add

```text
src/whirlwind/domain/filesystem/layout.py
src/whirlwind/domain/filesystem/metamosaictree.py
```

## 5.1 Add `RunTreeLayout`

File:

```text
src/whirlwind/domain/filesystem/layout.py
```

Shape:

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class RunTreeLayout:
    version: str = "runtree-v1"

    def manifest_dir(self, root: Path) -> Path:
        return root / "manifest"

    def root_manifest_path(self, root: Path, name: str) -> Path:
        return self.manifest_dir(root) / name

    def loose_mosaics_dir(self, root: Path) -> Path:
        return root / "mosaics"

    def mosaic_branch_dir(self, root: Path, mosaic_id: str) -> Path:
        return self.loose_mosaics_dir(root) / mosaic_id

    def metamosaics_dir(self, root: Path) -> Path:
        return root / "metamosaics"

    def metamosaic_dir(self, root: Path, metamosaic_id: str) -> Path:
        return self.metamosaics_dir(root) / metamosaic_id

    def metamosaic_branches_dir(self, root: Path, metamosaic_id: str) -> Path:
        return self.metamosaic_dir(root, metamosaic_id) / "branches"

    def metamosaic_branch_dir(
        self,
        root: Path,
        metamosaic_id: str,
        mosaic_id: str,
    ) -> Path:
        return self.metamosaic_branches_dir(root, metamosaic_id) / mosaic_id
```

## 5.2 Change `RunTree`

Add `layout`:

```python
@dataclass
class RunTree:
    root: Path
    manifest_dir: Path
    layout: RunTreeLayout
```

Change `plant()`:

```python
@classmethod
def plant(cls, root: str | Path, layout: RunTreeLayout | None = None) -> "RunTree":
    root = Path(root).expanduser().resolve()
    layout = layout or RunTreeLayout()
    tree = cls(
        root=root,
        manifest_dir=layout.manifest_dir(root),
        layout=layout,
    )
    return tree.ensure()
```

Add:

```python
def branch_for(self, record: MosaicRecord) -> MosaicBranch:
    if record.metamosaic_id:
        branch_dir = self.layout.metamosaic_branch_dir(
            self.root,
            record.metamosaic_id,
            record.mosaic_id,
        )
    else:
        branch_dir = self.layout.mosaic_branch_dir(
            self.root,
            record.mosaic_id,
        )
    return MosaicBranch.plant_at(branch_dir, record.mosaic_id)

def metamosaic_tree(self, metamosaic_id: str) -> MetamosaicTree:
    return MetamosaicTree.plant(
        self.layout.metamosaic_dir(self.root, metamosaic_id),
        metamosaic_id,
    )

def root_manifest_path(self, name: str = "manifest.csv") -> Path:
    return self.layout.root_manifest_path(self.root, name)
```

Keep this as a compatibility wrapper:

```python
def get_manifest_path_csv(self, name: str = "manifest.csv") -> Path:
    return self.root_manifest_path(name)
```

Deprecate direct `plant_mosaic_branch(file_id)`.

## 5.3 Change `MosaicBranch`

Add `plant_at()`:

```python
@classmethod
def plant_at(cls, mosaic_dir: Path, mosaic_id: str) -> "MosaicBranch":
    mosaic_dir = Path(mosaic_dir).expanduser().resolve()
    return cls(
        root=mosaic_dir.parent,
        file_id=mosaic_id,
        mosaic_dir=mosaic_dir,
        browse_dir=mosaic_dir / "browse",
        shards_dir=mosaic_dir / "shards",
        tiles_dir=mosaic_dir / "tiles",
        manifest_dir=mosaic_dir / "manifest",
        metadata_dir=mosaic_dir / "metadata",
        staging_dir=mosaic_dir / "staging",
    )
```

Keep old constructor as wrapper:

```python
@classmethod
def plant(cls, root: Path, file_id: str) -> "MosaicBranch":
    return cls.plant_at(root / file_id, file_id)
```

## 5.4 Add `MetamosaicTree`

File:

```text
src/whirlwind/domain/filesystem/metamosaictree.py
```

Shape:

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class MetamosaicTree:
    metamosaic_id: str
    root: Path
    branches_dir: Path
    manifest_dir: Path
    metadata_dir: Path

    @classmethod
    def plant(cls, root: Path, metamosaic_id: str) -> "MetamosaicTree":
        root = Path(root).expanduser().resolve()
        return cls(
            metamosaic_id=metamosaic_id,
            root=root,
            branches_dir=root / "branches",
            manifest_dir=root / "manifest",
            metadata_dir=root / "metadata",
        )

    def ensure(self) -> "MetamosaicTree":
        for p in (self.root, self.branches_dir, self.manifest_dir, self.metadata_dir):
            p.mkdir(parents=True, exist_ok=True)
        return self
```

## 5.5 Config changes

File:

```text
src/whirlwind/domain/config/defaults.py
```

Add:

```python
"runtree": {
    "layout": "runtree-v1",
    "manifest_name": "manifest.csv",
},
"metamosaic": {
    "build": {
        "stem": "mm",
        "mode": "link",
        "manifest_name": "metamosaic.csv",
        "root_manifest_name": "manifest.csv",
        "force": False,
    }
}
```

Also fix likely config inconsistency:

```text
Some builders reference ctx.section("manifest", "ids"),
but defaults currently define manifest/build and manifest/stats.
```

Either add:

```python
"manifest": {
    "ids": {"file_name": "manifest.csv"},
    "meta": {"file_name": "metadata.csv"},
    ...
}
```

or update builders to use the existing `manifest/build` and `manifest/stats`.

## 5.6 CommandContext changes

File:

```text
src/whirlwind/commands/context.py
```

Current:

```python
@property
def run_tree(self) -> RunTree:
    return RunTree.plant(self.dest_dir / self.run_id)
```

Target:

```python
@property
def run_tree(self) -> RunTree:
    layout = RunTreeLayout(
        version=str(self.value("runtree", "layout", default="runtree-v1"))
    )
    return RunTree.plant(self.dest_dir / self.run_id, layout=layout)
```

---

# 6. Phase 5 — Convert All Operations from Paths to MosaicRecords

## Goal

Remove raw path iteration and direct branch planting from all bridges.

## 6.1 General builder pattern

Current:

```python
manifest = IDManifest(manifest_path)
paths = manifest.paths()
return Request(..., paths=paths)
```

Target:

```python
manifest = IDManifest(manifest_path)
catalog = MosaicCatalog(manifest)
selector = selector_from_tokens(tv)
records = catalog.select(selector)
return Request(..., records=records)
```

## 6.2 General bridge pattern

Current:

```python
for p in request.paths:
    f = RasterFile(p)
    fid = f.file_id
    branch = MosaicBranch.plant(request.tree.root, fid)
```

Target:

```python
for record in request.records:
    branch = request.tree.branch_for(record).ensure()
```

Use:

```python
record.path
record.mosaic_id
record.source_uri
record.variant_id
record.date
```

instead of recomputing identity from the raster path.

---

## 6.3 Update downsample

### Files

```text
src/whirlwind/commands/builders/downsample_cmd.py
src/whirlwind/bridges/rasterops/downsample.py
```

### Current coupling

Builder creates `paths = manifest.paths()`.

Bridge loops paths, creates `RasterFile(p)`, gets `mosaic_id = f.file_id`, plants `MosaicBranch.plant(request.run_tree.root, mosaic_id)`, and writes browse output under `branch.browse_dir`.

### Changes

Request:

```python
@dataclass(frozen=True)
class Request:
    run_tree: RunTree
    spec: DSSpec
    manifest_path: Path
    records: Iterable[MosaicRecord]
    overwrite: bool = False
    display_range: bool = False
```

Bridge loop:

```python
for record in request.records:
    branch = request.run_tree.branch_for(record).ensure()
    out = branch.browse_dir / f"b{record.mosaic_id}.tif"

    downsampler = Downsampler.from_paths(
        src_path=record.path,
        out_path=out,
        spec=request.spec,
    )
```

Summary should store `mosaic_id`.

---

## 6.4 Update tile-plan staging

### Files

```text
src/whirlwind/commands/builders/stage_tesselation_cmd.py
src/whirlwind/bridges/staging/stage_tesselation.py
```

### Current coupling

Bridge loops over `request.paths`, creates `RasterFile(p)`, plants branch at root, writes `tile_plan.csv` into `branch.staging_dir`.

### Changes

Request:

```python
@dataclass(frozen=True)
class Request:
    spec: TSpec
    tree: RunTree
    manifest: IDManifest
    records: Iterator[MosaicRecord]
    force: bool
    plan_name: str = "tile_plan.csv"
```

Loop:

```python
for record in request.records:
    branch = request.tree.branch_for(record).ensure()
    out_path = branch.staging_dir / request.plan_name

    planner = WindowPlanner(record.path, request.spec)
    sink = WindowPlanCSV(out_path)
```

Summary:

```python
@dataclass(frozen=True)
class Summary:
    mosaic_id: str
    tiles_written: int
    skipped: bool
    out_path: Path
```

---

## 6.5 Update tessellation / shard writing

### Files

```text
src/whirlwind/commands/builders/tesselate_mosaics_cmd.py
src/whirlwind/bridges/rasterops/tesselate.py
```

### Current coupling

Builder passes `paths`.

`RasterTiler.__init__(p, request)` creates `RasterFile(p)`, gets `fid`, plants root branch, finds tile plan, then writes shards and tile manifest.

### Changes

Request:

```python
@dataclass(frozen=True)
class Request:
    spec: TSpec
    tree: RunTree
    manifest: IDManifest
    records: Iterable[MosaicRecord]
    prefix: str
    shard_size: int
    overwrite: bool
    label: bool
    dry: bool
    dpath_name: str
    plan_name: str
    manifest_name: str
    manifest_kind: str
```

`RasterTiler`:

```python
class RasterTiler:
    def __init__(self, record: MosaicRecord, request: Request) -> None:
        self.record = record
        self.p = record.path
        self.request = request

        f = RasterFile(record.path)
        self.encoder = TileEncoder(src=f)

        branch = request.tree.branch_for(record).ensure()
        self.shard_dir = branch.shards_dir
        self.gpkg_path = branch.browse_dir / request.dpath_name
        self.manifest_path = branch.manifest_dir / request.manifest_name
        self.tile_plan_path = branch.staging_dir / request.plan_name
```

Eventually `TileEncoder` should accept `MosaicRecord` directly so it does not recompute `RasterFile` identity.

Target later:

```python
self.encoder = TileEncoder.from_record(record)
```

Tile metadata should include:

```text
mosaic_id
branch_id
metamosaic_id
```

---

## 6.6 Update damage-path staging

### Files

```text
src/whirlwind/commands/builders/stage_damagepaths_cmd.py
src/whirlwind/bridges/staging/stage_damagepaths.py
```

### Current coupling

Bridge loops paths, uses `RasterFile(p, georefs=True)`, plants root branch, then creates `PathPlan.from_browse(branch, crs_wkt=f.crs_wkt)`.

### Changes

Request:

```python
@dataclass
class Request:
    tree: RunTree
    manifest_path: Path
    records: Iterator[MosaicRecord]
    overwrite: bool
    set_defaults: bool
```

Loop:

```python
for record in request.records:
    raster = RasterFile(record.path, georefs=True)
    branch = request.tree.branch_for(record).ensure()
    plan = PathPlan.from_browse(branch, crs_wkt=raster.crs_wkt)
```

Summary should include:

```text
mosaic_id
metamosaic_id
```

---

## 6.7 Update shard export

### Files

```text
src/whirlwind/commands/builders/export_shards_cmd.py
src/whirlwind/bridges/tiling/shards_to_tifs.py
```

### Current coupling

Bridge loops paths, creates `RasterFile(p)`, gets `fid`, plants root branch, then reads shards from `branch.shards_dir`.

### Changes

Request:

```python
@dataclass(frozen=True)
class Request:
    run_tree: RunTree
    manifest: IDManifest
    records: Iterable[MosaicRecord]
    shard_sub_dir: str | None = None
    ...
```

Loop:

```python
for record in request.records:
    branch = request.run_tree.branch_for(record).ensure()

    if request.shard_sub_dir:
        shard_dir = branch.shards_dir / request.shard_sub_dir
        out_dir = branch.tiles_dir / request.shard_sub_dir
    else:
        shard_dir = branch.shards_dir
        out_dir = branch.tiles_dir
```

Summary should include `mosaic_id`.

---

## 6.8 Update metadata discovery

### Files

```text
src/whirlwind/commands/builders/discover_metadata_cmd.py
src/whirlwind/bridges/catalogs/discovermetadata.py
```

### Current coupling

`DiscoverMetadataBridge._write_mode()` loops `manifest.paths()`, creates `RasterFile(raster_path)`, and calls `request.run_tree.plant_mosaic_branch(raster.mid)`.

### Changes

Request should include optional selector or selected records:

```python
@dataclass(frozen=True)
class Request:
    run_tree: RunTree
    manifest_name: str = "manifest.csv"
    records: Iterable[MosaicRecord] | None = None
    modes: tuple[MetadataMode, ...] = ("core",)
    file_format: str = "csv"
    force: bool = False
```

Inside `run()`:

```python
manifest = IDManifest(manifest_path)
records = request.records or manifest.records()
```

Inside `_write_mode()`:

```python
for record in records:
    branch = request.run_tree.branch_for(record).ensure()
    per_mosaic_path = branch.metadata_dir / f"{mode}-metadata.csv"

    metadata = GeoMetadataExtractor(
        path=record.path,
        mode=mode,
    ).discover()
```

The aggregate metadata file should include `mosaic_id` even if `GeoMetadataExtractor` does not return it:

```python
metadata["mosaic_id"] = record.mosaic_id
metadata["source_uri"] = record.source_uri
```

---

## 6.9 Update ID manifest writing

### Files

```text
src/whirlwind/commands/builders/write_id_manifest_cmd.py
src/whirlwind/bridges/catalogs/writeidmanifest.py
src/whirlwind/adapters/io/idmanifest.py
```

### Current behavior

Discovers raster files from input directory and writes `RasterFile.record()`.

### Changes

Keep this as the initial source manifest builder.

Add two modes later:

```text
source manifest
  Built from discovered source rasters.

run manifest
  Built from current RunTree branch/metamosaic organization.
```

Do not overload `IDManifest` too far. Prefer:

```text
IDManifest      -> source mosaic manifest
RunManifest     -> runtree branch/metamosaic manifest
TileManifest    -> per-branch tile/shard manifest
```

---

# 7. Phase 6 — Add Run Manifest Regeneration

## Goal

After branches are moved or linked into metamosaic trees, regenerate a root manifest describing the current RunTree state.

## New files

```text
src/whirlwind/adapters/io/runmanifest.py
src/whirlwind/domain/catalogs/runrecord.py
src/whirlwind/bridges/catalogs/refresh_runmanifest.py
src/whirlwind/commands/builders/refresh_runmanifest_cmd.py
```

## 7.1 Add `RunManifest`

File:

```text
src/whirlwind/adapters/io/runmanifest.py
```

Responsibilities:

```text
- write root-level branch/metamosaic manifest
- read root-level branch/metamosaic manifest
- rebuild from RunTree
```

Root manifest schema:

```text
mosaic_id
metamosaic_id
branch_id
source_uri
path
branch_path
browse_dir
shards_dir
tiles_dir
staging_dir
metadata_dir
tile_plan_path
tile_manifest_path
date
variant_id
variant_type
spectral_id
id_scheme
id_version
layout_version
```

## 7.2 Branch records

Each branch should get a small branch record file:

```text
branch.metadata_dir / "branch.json"
```

or:

```text
branch.manifest_dir / "branch.csv"
```

Recommended branch record fields:

```text
mosaic_id
metamosaic_id
branch_id
source_uri
source_path
branch_path
date
variant_id
variant_type
id_scheme
id_version
layout_version
created_at
```

This lets `RunManifest.refresh()` rebuild the root manifest without guessing from path names.

## 7.3 Add refresh command

Shell form:

```text
test manifest refresh
```

Later top-level:

```text
manifest refresh
```

Request:

```python
@dataclass(frozen=True)
class Request:
    run_tree: RunTree
    manifest_name: str = "manifest.csv"
    force: bool = False
```

Bridge behavior:

```text
1. Walk known branch records.
2. Build rows.
3. Write runtree root manifest.
4. Return count.
```

---

# 8. Phase 7 — Add Metamosaic Grouping

## Goal

Group overlapping mosaic branches into metamosaic trees and regenerate the root manifest.

## New files

```text
src/whirlwind/domain/geometry/footprints.py
src/whirlwind/domain/catalogs/overlapgraph.py
src/whirlwind/bridges/catalogs/build_metamosaics.py
src/whirlwind/commands/builders/build_metamosaic_cmd.py
```

Optional later:

```text
src/whirlwind/adapters/geo/footprint_index.py
```

## 8.1 Required input metadata

To build metamosaics, the catalog must have either:

```text
footprint
```

or enough data to compute one from source raster metadata.

Required row fields:

```text
mosaic_id
path
source_uri
footprint
srid
variant_id
date
```

If the source manifest does not have footprints, run metadata discovery first.

## 8.2 Add footprint parser

File:

```text
src/whirlwind/domain/geometry/footprints.py
```

Initial version can use bounding boxes if polygon parsing is not ready:

```python
@dataclass(frozen=True)
class Footprint:
    minx: float
    miny: float
    maxx: float
    maxy: float
    crs: str = "EPSG:4326"

    def intersects(self, other: "Footprint") -> bool:
        return not (
            self.maxx < other.minx
            or self.minx > other.maxx
            or self.maxy < other.miny
            or self.miny > other.maxy
        )
```

Later use shapely geometries for exact polygon intersection.

## 8.3 Add overlap graph

File:

```text
src/whirlwind/domain/catalogs/overlapgraph.py
```

Behavior:

```text
node = MosaicRecord
edge = footprints intersect
component = metamosaic group
```

Implementation outline:

```python
class OverlapGraph:
    @staticmethod
    def connected_components(records: Iterable[MosaicRecord]) -> list[list[MosaicRecord]]:
        ...
```

Use connected components.

Example:

```text
A overlaps B
B overlaps C
A does not overlap C
```

All three belong to one metamosaic.

## 8.4 Add `BuildMetamosaicsBridge`

File:

```text
src/whirlwind/bridges/catalogs/build_metamosaics.py
```

Request:

```python
@dataclass(frozen=True)
class Request:
    run_tree: RunTree
    records: Iterable[MosaicRecord]
    stem: str = "mm"
    mode: str = "link"        # "link" | "copy" | "move"
    force: bool = False
    refresh_root_manifest: bool = True
```

Behavior:

```text
1. Ensure RunTree.
2. Build overlap components from selected records.
3. For each component:
   - metamosaic_id = FileID.metamosaic(sorted(member_ids), stem)
   - create MetamosaicTree
   - for each member:
       old_branch = run_tree.branch_for(record)
       updated_record = record with metamosaic_id
       new_branch = run_tree.branch_for(updated_record)
       link/copy/move old branch -> new branch
       write branch record
   - write metamosaic manifest.
4. Optionally refresh root run manifest.
```

## 8.5 Move vs copy vs link

Recommended default:

```text
mode = "link"
```

Reasons:

```text
- safer than move
- avoids duplicate shard storage
- allows inspection before destructive cleanup
```

Supported behavior:

```text
link
  symlink or hardlink branch directory where supported

copy
  duplicate branch tree

move
  relocate branch tree and remove original
```

If links are not portable enough, use copy for first implementation.

## 8.6 Final target layout

```text
runtree/
  manifest/
    manifest.csv
    core-metadata.csv
    extended-metadata.csv

  mosaics/
    m-240119-DSM-a31f/
      browse/
      shards/
      tiles/
      manifest/
      metadata/
      staging/

  metamosaics/
    mm-denver-a9f031/
      metadata/
      manifest/
        metamosaic.csv
      branches/
        m-240119-DSM-a31f/
          browse/
          shards/
          tiles/
          manifest/
          metadata/
          staging/
        m-240119-RGB-b7c2/
          browse/
          shards/
          tiles/
          manifest/
          metadata/
          staging/
```

After confidence is high, you can remove or avoid `mosaics/` loose branches and place everything directly under metamosaics.

---

# 9. Phase 8 — Promote Commands Out of `Test`

## Goal

Stop routing all real commands through `test`.

## Files to change

```text
src/whirlwind/commands/__init__.py
src/whirlwind/entrypoint/__init__.py
src/whirlwind/commands/test.py
```

## 9.1 Add command families

Instead of only:

```python
from whirlwind.commands.test import Test
```

define top-level command routers:

```text
commands/manifest.py
commands/mosaic.py
commands/tile.py
commands/metamosaic.py
commands/export.py
```

Possible shell syntax:

```text
manifest ids
manifest metadata
manifest refresh

mosaic downsample
mosaic pathplan

tile plan
tile cut
tile export

metamosaic build
metamosaic refresh
```

## 9.2 Register commands in `bootstrapp`

Current:

```python
app = WhirlwindApp(cmds=[Test()], config=config)
```

Target:

```python
app = WhirlwindApp(
    cmds=[
        ManifestCommand(),
        MosaicCommand(),
        TileCommand(),
        MetamosaicCommand(),
        ExportCommand(),
        Test(),  # optional compatibility
    ],
    config=config,
)
```

Keep `Test` temporarily for aliases.

---

# 10. File-by-File Checklist

## `src/whirlwind/domain/filesystem/files.py`

Change:

```text
- Make FileID own mosaic, metamosaic, branch, tile, shard IDs.
- Make raster_file_id() a wrapper or remove it.
- Make RasterFile use FileID.mosaic().
- Change RasterFile.record() to write mosaic_id, source_uri, id_scheme, id_version.
- Ensure record path values are strings.
```

Referenced by:

```text
DiscoverFiles
IDManifest
TileEncoder
DownsampleBridge
StageTesselationBridge
TesselationBridge
DamagepathStagingBridge
ExportShardsBridge
DiscoverMetadataBridge
```

## `src/whirlwind/domain/geometry/tiles/tile.py`

Change:

```text
- Import FileID.
- Use FileID.tile() for tile IDs.
- Add mosaic_id / branch_id / metamosaic_id to tile metadata.
- Eventually allow TileEncoder.from_record(record).
```

Referenced by:

```text
TesselationBridge
ShardWriter
Tile manifest rows
Shard export
```

## `src/whirlwind/adapters/io/idmanifest.py`

Change:

```text
- Add rows().
- Add records().
- Change ids() to use mosaic_id.
- Keep compatibility fallback for file_id/id.
- Deprecate mids().
```

Referenced by:

```text
WriteIDManifestBridge
DiscoverMetadataBridge
DownsampleCommand
StageTesselationCommand
TesselationCommand
StagePathsCommand
ExportShardsCommand
MosaicCatalog
```

## `src/whirlwind/adapters/io/mosaiccatalog.py`

Add:

```text
- MosaicCatalog.records()
- MosaicCatalog.select(selector)
```

Referenced by all command builders that operate on mosaic sets.

## `src/whirlwind/domain/catalogs/mosaicrecord.py`

Add.

Referenced by:

```text
MosaicCatalog
RunTree
RunManifest
DownsampleBridge
StageTesselationBridge
TesselationBridge
DamagepathStagingBridge
ExportShardsBridge
DiscoverMetadataBridge
MetamosaicBuilder
```

## `src/whirlwind/domain/catalogs/mosaicselector.py`

Add.

Referenced by:

```text
commands/selectors.py
MosaicCatalog
all operation command builders
```

## `src/whirlwind/commands/bridge.py`

Change:

```text
- Extend TokenView to parse key-value options.
- Add values() helper.
```

Referenced by all command builders.

## `src/whirlwind/commands/selectors.py`

Add.

Referenced by:

```text
downsample_cmd.py
stage_tesselation_cmd.py
tesselate_mosaics_cmd.py
stage_damagepaths_cmd.py
export_shards_cmd.py
discover_metadata_cmd.py
build_metamosaic_cmd.py
```

## `src/whirlwind/domain/filesystem/layout.py`

Add.

Referenced by:

```text
RunTree
CommandContext
tests
```

## `src/whirlwind/domain/filesystem/runtree.py`

Change:

```text
- Add layout.
- Add branch_for(record).
- Add metamosaic_tree(metamosaic_id).
- Add root_manifest_path().
- Keep get_manifest_path_csv() compatibility wrapper.
- Deprecate direct plant_mosaic_branch(file_id).
```

Referenced by almost every bridge.

## `src/whirlwind/domain/filesystem/mosaicbranch.py`

Change:

```text
- Add plant_at(mosaic_dir, mosaic_id).
- Keep plant(root, file_id) wrapper.
- Prefer mosaic_id naming over file_id internally if possible.
```

Referenced by:

```text
RunTree
legacy bridges until migrated
```

## `src/whirlwind/domain/filesystem/metamosaictree.py`

Add.

Referenced by:

```text
RunTree
BuildMetamosaicsBridge
RunManifest refresh
```

## `src/whirlwind/commands/context.py`

Change:

```text
- Build RunTree with RunTreeLayout.
- Read layout config.
```

Referenced by all command builders.

## `src/whirlwind/domain/config/defaults.py`

Change:

```text
- Add runtree section.
- Add metamosaic section.
- Normalize manifest config names.
```

Also fix likely config inconsistency:

```text
Some builders reference ctx.section("manifest", "ids"),
but defaults currently define manifest/build and manifest/stats.
```

Either add:

```python
"manifest": {
    "ids": {"file_name": "manifest.csv"},
    "meta": {"file_name": "metadata.csv"},
    ...
}
```

or update builders to use the existing `manifest/build` and `manifest/stats`.

## `src/whirlwind/commands/builders/downsample_cmd.py`

Change:

```text
- Build MosaicSelector from TokenView.
- Build MosaicCatalog from IDManifest.
- Pass records instead of paths.
```

## `src/whirlwind/bridges/rasterops/downsample.py`

Change:

```text
- Request.records instead of Request.paths.
- Use run_tree.branch_for(record).
- Use record.path and record.mosaic_id.
```

## `src/whirlwind/commands/builders/stage_tesselation_cmd.py`

Change:

```text
- Build selector/catalog.
- Pass records.
```

## `src/whirlwind/bridges/staging/stage_tesselation.py`

Change:

```text
- Request.records instead of paths.
- Use tree.branch_for(record).
- Use record.path for WindowPlanner.
- Summary includes mosaic_id.
```

## `src/whirlwind/commands/builders/tesselate_mosaics_cmd.py`

Change:

```text
- Build selector/catalog.
- Pass records.
```

## `src/whirlwind/bridges/rasterops/tesselate.py`

Change:

```text
- Request.records instead of paths.
- RasterTiler accepts MosaicRecord, not Path.
- Use tree.branch_for(record).
- Use record metadata in tile metadata.
```

## `src/whirlwind/commands/builders/stage_damagepaths_cmd.py`

Change:

```text
- Build selector/catalog.
- Pass records.
```

## `src/whirlwind/bridges/staging/stage_damagepaths.py`

Change:

```text
- Request.records instead of paths.
- Use tree.branch_for(record).
- Use RasterFile(record.path, georefs=True) only for georef metadata.
```

## `src/whirlwind/commands/builders/export_shards_cmd.py`

Change:

```text
- Build selector/catalog.
- Pass records.
```

## `src/whirlwind/bridges/tiling/shards_to_tifs.py`

Change:

```text
- Request.records instead of paths.
- Use tree.branch_for(record).
- Use branch paths from RunTree, not direct MosaicBranch.plant().
```

## `src/whirlwind/commands/builders/discover_metadata_cmd.py`

Change:

```text
- Optionally support MosaicSelector.
- Pass selected records to DiscoverMetadataBridge.
```

## `src/whirlwind/bridges/catalogs/discovermetadata.py`

Change:

```text
- Use manifest.records() or request.records.
- Use tree.branch_for(record).
- Write mosaic_id/source_uri into metadata rows.
```

## `src/whirlwind/commands/builders/write_id_manifest_cmd.py`

Change:

```text
- Keep as source manifest writer.
- Ensure output schema is mosaic_id-based.
- Consider renaming command from "ids" to "manifest ids" later.
```

## `src/whirlwind/bridges/catalogs/writeidmanifest.py`

Change:

```text
- Continue using IDManifest.write_from().
- Return manifest path.
- Confirm source manifest schema.
```

---

# 11. Metamosaic Command Outline

## Command builder file

```text
src/whirlwind/commands/builders/build_metamosaic_cmd.py
```

Pseudo-shape:

```python
class BuildMetamosaicRequest(RequestBuilder[Request]):
    def from_tokens(self, tokens: list[str], config: Config) -> Request:
        tv = TokenView.parse(tokens)
        ctx = CommandContext(config)

        manifest_name = ctx.section("manifest", "ids").get("file_name", "manifest.csv")
        manifest = IDManifest(ctx.run_tree.get_manifest_path_csv(manifest_name))

        catalog = MosaicCatalog(manifest)
        selector = selector_from_tokens(tv)
        records = catalog.select(selector)

        mm_cfg = ctx.section("metamosaic", "build")

        return Request(
            run_tree=ctx.run_tree,
            records=records,
            stem=str(mm_cfg.get("stem", "mm")),
            mode=str(mm_cfg.get("mode", "link")),
            force=tv.has("-f", "--force"),
            refresh_root_manifest=True,
        )
```

## Bridge file

```text
src/whirlwind/bridges/catalogs/build_metamosaics.py
```

Pseudo-behavior:

```python
class BuildMetamosaicsBridge:
    def run(self, request: Request) -> Result:
        records = tuple(request.records)
        components = OverlapGraph.connected_components(records)

        summaries = []

        for component in components:
            member_ids = tuple(sorted(r.mosaic_id for r in component))
            metamosaic_id = FileID.metamosaic(member_ids, stem=request.stem)
            mm_tree = request.run_tree.metamosaic_tree(metamosaic_id).ensure()

            for record in component:
                old_branch = request.run_tree.branch_for(record)

                updated = replace(record, metamosaic_id=metamosaic_id)
                new_branch = request.run_tree.branch_for(updated).ensure()

                relocate_branch(
                    old_branch=old_branch,
                    new_branch=new_branch,
                    mode=request.mode,
                    force=request.force,
                )

                write_branch_record(new_branch, updated, request.run_tree.layout.version)

            write_metamosaic_manifest(mm_tree, component)

        if request.refresh_root_manifest:
            RunManifest.from_tree(request.run_tree).write()

        return Result(...)
```

---

# 12. Migration Safety Rules

## 12.1 No downstream parsing of mosaic IDs

Do not write logic like:

```python
if mosaic_id.startswith("m-"):
    ...
```

Use record fields:

```python
record.variant_id
record.date
record.id_scheme
```

## 12.2 No bridge-level branch path construction

Do not use:

```python
MosaicBranch.plant(request.tree.root, fid)
```

Use:

```python
request.tree.branch_for(record)
```

## 12.3 No operation should consume only `Path`

Operations that are tied to a mosaic should consume:

```python
MosaicRecord
```

Raw `Path` is acceptable only for low-level adapters like:

```text
RasterioWindowReader
Downsampler
GeoMetadataExtractor
WindowPlanner
```

## 12.4 Root manifest should not be the same as tile manifest

Use separate concepts:

```text
IDManifest
  Source rasters discovered from input directory.

RunManifest
  Current runtree organization: branches and metamosaics.

TileManifest
  Per-branch tile/shard samples.
```

## 12.5 Layout changes must be isolated

Only these files should know physical directory structure:

```text
RunTreeLayout
RunTree
MosaicBranch
MetamosaicTree
RunManifest refresh
```

Everything else asks for paths from those objects.

---

# 13. Suggested Implementation Order

## Step 1

Implement `FileID.mosaic()`, `FileID.tile()`, `FileID.metamosaic()`.

Then change:

```text
RasterFile
TileEncoder
RasterFile.record()
IDManifest.ids()
```

Run:

```text
test ids -f -v
```

Expected result:

```text
manifest has mosaic_id column
mosaic IDs are readable
tile IDs still generate
```

## Step 2

Add `MosaicRecord`, `IDManifest.records()`, and `MosaicCatalog`.

Run a small script or shell command to verify:

```text
manifest -> records -> record.mosaic_id/path/variant/date
```

## Step 3

Add `TokenView.options`, `MosaicSelector`, and `selector_from_tokens()`.

Verify selectors independently:

```text
--mosaic=...
--variant=DSM
--date=240119
```

## Step 4

Add `RunTreeLayout`, `MosaicBranch.plant_at()`, and `RunTree.branch_for()`.

Do not migrate all bridges yet.

Verify:

```text
record without metamosaic_id -> runtree/mosaics/<mosaic_id>
record with metamosaic_id    -> runtree/metamosaics/<mmid>/branches/<mosaic_id>
```

## Step 5

Migrate bridges in this order:

```text
1. DiscoverMetadataBridge
2. DownsampleBridge
3. StageTesselationBridge
4. DamagepathStagingBridge
5. TesselationBridge
6. ExportShardsBridge
```

Reason:

```text
metadata and downsample are simpler
tile planning precedes tessellation
export depends on shards already existing
```

## Step 6

Add `RunManifest.refresh`.

Verify root manifest can be regenerated from branch records.

## Step 7

Add `BuildMetamosaicsBridge`.

Start with `mode="copy"` for safety.

Then test:

```text
1. build source manifest
2. discover metadata/footprints
3. create loose mosaic branches
4. build metamosaics
5. refresh root manifest
6. run selected operation with --metamosaic=<id>
```

## Step 8

Promote commands out of `Test`.

---

# 14. Minimal Acceptance Criteria

The refactor is successful when all of these are true:

```text
1. Changing FileID.mosaic() changes mosaic naming everywhere.

2. No bridge directly constructs MosaicBranch with request.tree.root.

3. All mosaic operations can run with:
   --mosaic=<id>
   --variant=<variant>
   --date=<date>
   --metamosaic=<id>

4. Root manifest can be regenerated from RunTree.

5. Metamosaic grouping creates:
   runtree/metamosaics/<metamosaic_id>/branches/<mosaic_id>/

6. Tile manifests still live inside mosaic branches.

7. Tile IDs are generated by FileID.tile().

8. Directory layout changes are isolated to:
   RunTreeLayout
   RunTree
   MosaicBranch
   MetamosaicTree
   RunManifest
```

---

# 15. Red Flags to Remove During Review

Search for these patterns after each phase:

```text
MosaicBranch.plant(request.tree.root
MosaicBranch.plant(request.run_tree.root
manifest.paths()
RasterFile(p)
f.file_id
raster.mid
"mids"
_column("id")
root / file_id
root / mosaic_id
```

Not all uses are immediately wrong, but each should be reviewed.

Allowed low-level uses:

```text
RasterFile(record.path)
WindowPlanner(record.path, ...)
RasterioWindowReader(record.path)
GeoMetadataExtractor(path=record.path, ...)
Downsampler.from_paths(src_path=record.path, ...)
```

Disallowed high-level uses:

```text
Using RasterFile(path) just to recover mosaic_id.
Using path names to infer branch locations.
Using string parsing to infer variant/date/metamosaic.
```

---

# 16. Final Target Mental Model

```text
FileID
  Controls naming.

MosaicRecord
  Controls identity and selection fields.

MosaicSelector
  Controls which mosaics an operation touches.

MosaicCatalog
  Converts manifests into MosaicRecords.

RunTreeLayout
  Controls physical directory organization.

RunTree
  Resolves logical records into filesystem branches.

MosaicBranch
  Owns one mosaic's outputs.

MetamosaicTree
  Owns a spatial overlap group of MosaicBranches.

RunManifest
  Records current branch/metamosaic organization.

Bridge
  Performs one operation on selected MosaicRecords.
```

This structure lets you change:

```text
mosaic naming
runtree structure
branch organization
metamosaic grouping
command selection syntax
manifest layout
```

without rewriting raster IO, tile reading, shard writing, or downstream export logic.
