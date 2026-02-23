
# W:HIRLWIND
w:hirlwind is a recursive acronym that also describes its function:
`WHIRLWIND: Helps Ingest, Relate, Label, Wrangle, Index, Normalize Datacubes`
## program overview
the primary goal of w:hirlwind is to serve as a coordinating program between an unorganized drive and a database of datacubes or "metamosaics".
- `unorganized_drive -> ` **whirlwind.py** `-> metamosaic.db`

given an unorganized bucket of rasters, vectors, geotags, etc **w:hirlwind** performs the taks of *INGESTING* these data from the unorganized bucket to local object storage or a cloud bucket, *RELATING* mosaics, vectors, tiles, and other geographic data entities to one another through a "metamosaic" datacube, *LABELING* data with labels to be used in future machine learning tasks, *WRANGLING* the pixels, vector data, and metadata into a regular (i.e. standardized) directory/database convention, providing *INDEXES* for fast lookups, and *NORMALIZING* by reducing redundancy, insuring data integrity, and providing a unique primary key for each metamosaic stack. 

## directory overview:
 - `toolbox.py`
 - `cli.py`
 - `paint.py`

## dtypes
### the idea of a metamosaics
w:hirlwind helps organize geodata using a datacube abstraction, what we will call a *metamosaic*. these *metamosaics* are georeferenced collections of orthomosaics, tiles, vectors, annotations, etc. every metamosaic is confined to a precise spatial footprint over a small temporal period, but two metamosaics might contain a vastly different array of orthomosaics, tiles, and vector data depending on the collection efforts from that footprint. 
![metamosaic](assets/metamosaic.png)


# toolbox

------------------------------------------------------------------------

### Overview

`toolbox.py` provides helper utilities for `cli.py`, the command line front-end for w:hirlwind. The available functions include:

## 1) SCAN

Recursively walks a root directory to:

-   Count directories
-   Identify `.tif` / `.tiff` files
-   Compute total byte size across GeoTIFFs
-   Track the top-N largest files

*For each GeoTIFF discovered:*

-   Opens with GDAL in read-only mode
-   Extracts header-level metadata
-   Computes spatial footprint -- needs work
-   Emits structured CSV rows as a `scan_metadata_fingerprint.csv`

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
-   Top-N largest files

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
### Requirements
### Usage
### INGEST flow
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



