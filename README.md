## program overview
# W:HIRLWIND
w:hirlwind is a recursive acronym that also describes its function:
`WHIRLWIND: Helps Ingest, Relate, Label, Wrangle, Index, Normalize Datacubes`

The primary goal of **w:hirlwind** is to serve as a coordinating program
between an **unorganized drive** and a **database of datacubes or
"metamosaics"**.

    unorganized_drive  ->  whirlwind.py  ->  metamosaic.db

Given an unorganized bucket of rasters, vectors, geotags, etc.,
**w:hirlwind** performs the tasks of:

-   **INGESTING** data from the unorganized bucket to local object
    storage or cloud buckets
-   **RELATING** mosaics, vectors, tiles, and geographic entities
-   **LABELING** data for future machine learning tasks
-   **WRANGLING** pixel data and metadata into a regular
    directory/database structure
-   **INDEXING** spatial and metadata relationships
-   **NORMALIZING** datasets to ensure consistency and reduce redundancy

------------------------------------------------------------------------

# directory overview

    toolbox.py
    cli.py
    paint.py
    scanner.py
    injester.py

Each module provides a focused component of the WHIRLWIND pipeline.

------------------------------------------------------------------------

# dtypes

## the idea of a metamosaic

WHIRLWINDs `relate` feature organizes geodata using a **datacube abstraction** called a
**metamosaic**.

A *metamosaic* is a georeferenced collection of:

-   orthomosaics
-   tiles
-   vectors
-   annotations
-   metadata

Each metamosaic corresponds to:

-   a **fixed spatial footprint** of defined georeferenced geometry
-   a **small temporal window**

However, different metamosaics may contain different combinations of
orthomosaics, vector layers, and tiles depending on the collection
effort over that footprint.

![metamosaic](assets/metamosaic.png)

------------------------------------------------------------------------

# toolbox

------------------------------------------------------------------------

## Overview

`toolbox.py` provides **core utility functions** used across the
WHIRLWIND codebase.

It acts as the **shared infrastructure layer** supporting:

-   CLI command dispatch
-   filesystem traversal
-   metadata extraction
-   GeoTIFF metadata inspection
-   tile ID generation
-   logging and debugging
-   helper utilities used by scanner and ingest pipelines


------------------------------------------------------------------------

## Responsibilities

`toolbox.py` provides utilities for:

### Command Dispatch

Routes CLI commands to their execution pipelines.

    dispatch_scan()
    dispatch_ingest()

------------------------------------------------------------------------

### Filesystem Utilities

Utilities for navigating dataset directories.

Functions include:

    find_root()
    iter_tifs()
    iter_uris()
    makedir()

Capabilities:

-   recursively locate GeoTIFFs
-   read URIs from metadata CSV
-   create required output directories
-   identify project root paths

------------------------------------------------------------------------

### Metadata Extraction

GeoTIFF metadata extraction is handled through GDAL.

Primary functions:

    write_metadata()
    extract_metadata()
    load_metadata_csv()

Metadata fields include:

-   mosaic_id
-   uri
-   byte_size
-   crs
-   srid
-   raster dimensions
-   band count
-   dtype
-   nodata
-   spatial footprint
-   acquisition time
-   creation timestamp

------------------------------------------------------------------------

### Dataset Identity Utilities

Deterministic identifiers are generated for datasets and tiles.

    uuid_from_path()
    gen_tile_id()
    gen_fingerprint()

------------------------------------------------------------------------

### Logging

WHIRLWIND logs events to:

    logs/wind.log

Each entry contains:

    timestamp | message

------------------------------------------------------------------------

# paint

------------------------------------------------------------------------

## Overview

`paint.py` provides **terminal rendering utilities** used throughout
WHIRLWIND.

It wraps the `rich` library to standardize:

-   CLI output
-   progress bars
-   status indicators
-   tables
-   directory tree rendering
-   formatted terminal panels

All user-facing CLI output is routed through `paint.py`.

------------------------------------------------------------------------

## Message Rendering

Terminal messages are printed using stylized panels.

Available message types:

    paint.info()
    paint.ok()
    paint.warn()
    paint.err()
    paint.error_msg()

------------------------------------------------------------------------

## Progress Bars

Long running operations use progress bars.

    paint.progress()
    paint.new_task()
    paint.advance()

Common use cases:

-   scanning directories
-   metadata extraction
-   ingest pipelines

------------------------------------------------------------------------

## Tables

Formatted CLI reports use Rich tables.

    paint.set_table()
    paint.group()

Tables commonly render:

-   scan summaries
-   largest file lists
-   metadata reports

------------------------------------------------------------------------

## Directory Trees

`paint.py` can render directory structures for debugging and inspection.

    print_dir_tree_panel()
    dir_tree()



### 1) SCANNER 

Recursively walks a root directory to:

-   Count directories
-   Identify `.tif` / `.tiff` files
-   Generate CSV with file metadata to use for scan reporting

*For each GeoTIFF discovered:*

-   Opens with GDAL in read-only mode
-   Extracts header-level metadata
-   Computes spatial footprint -- needs work
-   Emits structured CSV rows as a `scan_metadata_fingerprint.csv`
-   Reads from structured CSV to report results of scan 

All operations are safe for very large raster files because no pixel
arrays are read.

------------------------------------------------------------------------

### Requirements

-   Python 3.10+
-   GDAL (Python bindings via `osgeo.gdal`, `osgeo.osr`)
-   `rich`
-   Local `paint` module (for terminal formatting)

Install Python dependencies:

``` bash
pip install rich
```

Ensure GDAL is installed and accessible in your environment.

------------------------------------------------------------------------

### Usage
After sourcing `.venv/bin/activate`:
``` bash
whirlwind scan --root /path/to/mosaics --top_n 500
```

###  _arguments

  Argument    Type     Description
  ----------- -------- ----------------------------------
  `--root`    string   Root directory to scan

-----------------------------------------------------------------------

### SCAN flow

When `scan` is executed:

1.  The root directory is resolved and validated.
2.  The directory tree is recursively traversed using `os.walk`.
3.  All `.tif` / `.tiff` files are identified.
4.  File sizes are read using filesystem metadata only.
5.  Statistics are accumulated.
6.  A Rich-formatted report is printed.
7.  Exit code `0` is returned on success.

If the root directory is invalid, exit code `2` is returned.

------------------------------------------------------------------------

### Terminal Report

The scan report includes:

-   Number of directories scanned
-   Number of GeoTIFF files
-   Total size across all GeoTIFFs
-   Top-N largest files with associated filetype, band count, etc

Rendered using Rich components such as:

-   `Table`
-   `Panel.fit`
-   `Align`
-   `Group`

------------------------------------------------------------------------

## Metadata Export

Mosaic metadata export is handled by:

`write_csv_mosaics(input_dir, out_csv, columns=None)`

Each row in the CSV represents one GeoTIFF.

### Default Schema

-   `mosaic_id`
-   `uri`
-   `uri_etag`
-   `byte_size`
-   `crs`
-   `srid`
-   `pixel_width`
-   `pixel_height`
-   `band_count`
-   `dtype`
-   `nodata`
-   `footprint`
-   `acquired_at`
-   `created_at`

------------------------------------------------------------------------

## Metadata Fields

### mosaic_id

Deterministic UUIDv5 derived from the file URI.

### uri

Full file path.

### uri_etag

Currently unused (placeholder for future versioning).

### byte_size

Filesystem-reported file size (local paths only).

### crs

CRS WKT from GDAL.

### srid

EPSG authority code extracted from CRS if available.

### pixel_width / pixel_height

Raster dimensions.

### band_count

Number of raster bands.

### dtype

Data type of band 1.

### nodata

Nodata value of band 1, if defined.

### footprint

EWKT polygon of raster bounds, reprojected to EPSG:4326.

### acquired_at

Parsed from filename prefix `YYMMDD_loc_...` and converted to ISO format
`20YY-MM-DD`.

### created_at

Timestamp at metadata extraction time (ISO format).

------------------------------------------------------------------------

### Estimated Performance Characteristics

  Operation             Memory Usage   IO Pattern
  --------------------- -------------- --------------------------
  Directory scan        Minimal        Filesystem metadata only
  Metadata extraction   Minimal        GDAL header reads
  CSV writing           Small          Sequential disk write

No raster pixel arrays are loaded into memory.

------------------------------------------------------------------------

### Design Principles

#### Memory Safety

-   Filesystem `stat()` for file sizes
-   GDAL header-only access
-   No full-raster reads

#### Deterministic Identity

-   UUIDv5 derived from URI
-   Stable per path string

#### CRS Normalization

-   Footprints should always be emitted as `EPSG:4326 EWKT`

------------------------------------------------------------------------

### Known Issues

-   `dispatch()` references `root` in error message without defining it.
-   `render_scan_report()` may reference `console` without
    instantiation.
-   `write_csv_mosaics()` accumulates rows in memory before writing.
-   `uri_etag` is currently unused, will probably reference directory versioning index.
-   `parse_columns()` is marked incomplete.

------------------------------------------------------------------------

### Intended Use Cases

-   Inventorying orthomosaic archives upon receipt of unstructured drive
-   Preparing data for populating database
-   Building spatial metadata catalogs for metamosaic emission
-   Auditing large GeoTIFF repositories for superlarge file entitites
-   Pre-indexing datasets before chip extraction, will probably be used in `INGEST`

------------------------------------------------------------------------
## 2) INGEST

`injester.py` implements the **WHIRLWIND ingestion pipeline**.

The ingest system converts GeoTIFF mosaics into **machine learning ready
tile datasets**.

The ingestion process produces:

-   WebDataset shards
-   tile metadata manifests
-   geospatial metadata for each tile

All operations use **windowed raster reads** to ensure scalability for
extremely large mosaics.

------------------------------------------------------------------------

## Requirements

-   Python 3.10+
-   rasterio
-   numpy
-   pyarrow

Install dependencies:

    pip install rasterio numpy pyarrow

------------------------------------------------------------------------

## Usage

    whirlwind ingest tiles --input /path/to/mosaics --out out/

or using metadata from a scan:

    whirlwind ingest tiles --input-csv metadata/scan_xxxx.csv --out out/

------------------------------------------------------------------------

## Default Output Structure

    out/
       shards/
          tiles-000000.tar
          tiles-000001.tar
          ...
       manifest.parquet
       ingest.json

Each shard contains:

    <tile_id>.npy
    <tile_id>.json

------------------------------------------------------------------------

## Tile Format

### Tile Array

    (bands, height, width)

Supported dtypes:

-   float32
-   uint16
-   uint8

------------------------------------------------------------------------

### Tile Metadata

Each tile includes:

-   source mosaic URI
-   CRS
-   affine transform
-   spatial bounds
-   tile window offsets
-   band count
-   data type

------------------------------------------------------------------------

## Quantization and Scaling

Available normalization strategies:

  Mode         Description
  ------------ --------------------------------------
  none         raw pixel values
  minmax       linear scaling using sampled min/max
  percentile   robust scaling using percentiles

Scaling statistics are estimated using sampled windows to avoid full
raster scans.

------------------------------------------------------------------------

## INGEST Flow

1.  Input GeoTIFF URIs are discovered.
2.  Each mosaic is opened using rasterio.
3.  A deterministic tiling grid is generated.
4.  Raster data is read using windowed reads.
5.  Pixel scaling and quantization are applied.
6.  Tile arrays and metadata are written into shard archives.
7.  A tile manifest is generated.
8.  An ingestion summary is written to `ingest.json`.

------------------------------------------------------------------------

## Estimated Performance Characteristics

  Operation            Memory Usage   IO Pattern
  -------------------- -------------- -------------------
  raster reads         bounded        windowed reads
  shard writing        small          sequential writes
  scaling estimation   small          sparse sampling

Memory usage scales with **tile size**, not mosaic size.

------------------------------------------------------------------------

## Intended Use Cases

-   preparing orthomosaic datasets for machine learning
-   converting GeoTIFF archives into tile datasets
-   generating WebDataset training corpora
-   building tile manifests for spatial indexing
-   normalizing imagery datasets for ML pipelines

------------------------------------------------------------------------
## 3) RELATE 
### Requirements
### Usage
### flow

------------------------------------------------------------------------
## 4) LABEL
### Requirements
### Usage
###  flow

------------------------------------------------------------------------
## 4) WRANGLE
### Requirements
### Usage
###  flow

------------------------------------------------------------------------
## 4) INDEX
### Requirements
### Usage
###  flow

------------------------------------------------------------------------
## 4) NORMALIZE
### Requirements
### Usage
###  flow



