# Logic README

## StageBuilder

**Goal:**  
- Given a directory of GeoTIFF/COG files (`.tif` / `.tiff`), produce a CSV with columns for mosaic and tile staging

focus: metadata extraction at both a mosaic and tile resolution. This script should capture:
- where the file is (`uri`)
- basic raster shape in pixels (`width`, `height`, `band_count`)
- `dtype`, `nodata`
- CRS info (WKT / SRID if available)
- a footprint polygon in an EPSG CRS (typically EPSG:4326) for spatial indexing/search

expected arguments: 
- `-m` expects `m` or `t` for mosaic or tile. This loads different headers for `mosaic_stage`
        or `tile_stage`. 
- `-d` root directory to recursively search through 
- `-o` output file (conventionally `version.csv`)
- `-v` verbosity: default `False`, if `True` gives verbose output. helpful for debugging

---

## ToolBox

**Goal:** Helper functions

- `get_dtype(gdal_type: int) -> str`  
  - Converts GDAL band dtype enum to a string  
  - Example: `GDT_UInt16` → `"UInt16"`

- `parse_acquired_at(metadata: Dict[str, str], path: Path) -> str`  
  - Tries to determine acquisition time from filename or metadata  
  - Expects filename pattern like: `YYMMDD_loc_...` (customize as needed)

- `get_footprint(...) -> str`  
  - Computes raster footprint and returns EWKT  
  - Example: `SRID=4326;POLYGON((...))`
- 'read_columns(File: file) -> List[str]'
  - Read from a file containing all columns 
- `extract_metadata(uri: str, columns: List[str]) -> Dict[str, Any]`  
  - Given a `uri` and a list of desired columns:  
    - opens raster using GDAL  
    - returns a dictionary of extracted metadata

- `iter_tifs(root: Path) -> Iterable[Path]`  
  - Recursively walks a directory and yields `.tif` / `.tiff` paths (or URIs)

- `write_csv(input_dir: str, out_csv: str) -> None`  
  - Reads all TIFFs under `input_dir`  
  - Extracts metadata from each  
  - Writes rows to `out_csv`
