-- bootstrap a *local* sqlite database for storing raster (GeoTIFF/COG) metadata,
--          pixel "views", precomputed tiles, and annotations.
--
-- assumptions:
--   - generate mosaic_id (uuid strings) in python
--   - provides fast bbox queries for tiles using sqlite rtree
--   - store geometry as EWKT text (ex: "SRID=4326;MULTIPOLYGON(...)")
--
-- run with:
--   sqlite3 wirlwind.db < initialize_sqlite.sql

-- =========================
--       SQLITE SETUP
-- =========================
PRAGMA FOREIGN_KEYS = ON;                -- enforce foreign keys for this connection
PRAGMA JOURNAL_MODE = WAL;               -- better concurrent read/write behavior (persists in db)
PRAGMA SYNCHRONOUS = NORMAL;             


-- =========================
--         MOSAIC
-- =========================
-- a "mosaic" is a raster source (orthomosaic image), with one per row
CREATE TABLE IF NOT EXISTS mosaic (

  mosaic_id TEXT PRIMARY KEY,            -- uuid string (generated in python, required)
  uri TEXT NOT NULL,                     -- path/uri to raster (local path recommended)
  uri_etag TEXT,                         -- optional change token (s3/http etag, etc)
  byte_size INTEGER,                     -- postgres bigint -> sqlite integer

  crs TEXT,                              -- CRS WKT/PROJJSON
  srid INTEGER,                          -- EPSG code when known
  pixel_width INTEGER NOT NULL,          -- raster width in pixels
  pixel_height INTEGER NOT NULL,         -- raster height in pixels
  band_count INTEGER NOT NULL,           -- number of raster bands
  dtype TEXT,                            -- pixel dtype string
  nodata REAL,                           -- nodata value (if any)

  footprint TEXT NOT NULL,               -- EWKT text: "SRID=4326;MULTIPOLYGON(...)"

  acquired_at TEXT,                      
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS mosaic_uri_uk
  ON mosaic (uri);

CREATE INDEX IF NOT EXISTS mosaic_created_idx
  ON mosaic (created_at);


-- =========================
--          VIEW
-- =========================
-- A "view" is a rectangular region in pixel coordinates within a mosaic, unconstrained by tiles
CREATE TABLE IF NOT EXISTS view (

  view_id INTEGER PRIMARY KEY AUTOINCREMENT,  

  mosaic_id TEXT NOT NULL
    REFERENCES mosaic(mosaic_id)
    ON DELETE CASCADE,

  x_ori INTEGER NOT NULL,                 -- pixel x of top-left corner
  y_ori INTEGER NOT NULL,                 -- pixel y of top-left corner
  width INTEGER NOT NULL,                 -- width in pixels
  height INTEGER NOT NULL,                -- height in pixels

  footprint TEXT,                         -- optional EWKT footprint (if you compute it)
  quality_score REAL,                     -- optional score

  created_at TEXT NOT NULL DEFAULT (datetime('now')),

  CHECK (x_ori >= 0),
  CHECK (y_ori >= 0),
  CHECK (width > 0),
  CHECK (height > 0)
);

CREATE INDEX IF NOT EXISTS view_mosaic_idx
  ON view (mosaic_id);

CREATE INDEX IF NOT EXISTS view_created_idx
  ON view (created_at);


-- =========================
--       TILE METADATA
-- =========================
-- a tile is a precomputed subset of a mosaic. the tile file + thumbnail live on disk.
-- this table stores metadata and lookup keys and lives in wirlwind.db
CREATE TABLE IF NOT EXISTS tile_metadata (

  _id INTEGER PRIMARY KEY AUTOINCREMENT,  -- sqlite replacement for bigserial (used by rtree)

  mosaic_id TEXT NOT NULL
    REFERENCES mosaic(mosaic_id)
    ON DELETE CASCADE,

  -- z/x/y hierarchy (optional, but recommended if you use an xyz-style addressing)
  z INTEGER NOT NULL,
  x INTEGER NOT NULL,
  y INTEGER NOT NULL,

  tile_width INTEGER NOT NULL,            -- tile width in pixels
  tile_height INTEGER NOT NULL,           -- tile height in pixels
  overlap INTEGER NOT NULL DEFAULT 0,     -- overlap pixels used during tile generation

  annotation TEXT,                        -- free-form label / comment
  tile_uri TEXT NOT NULL,                 -- tile file path
  tile_uri_etag TEXT,                     -- optional change token

  footprint TEXT NOT NULL,                -- EWKT footprint for reference/debugging

  nodata_frac REAL,                       -- fraction of nodata pixels (0..1)
  created_at TEXT NOT NULL DEFAULT (datetime('now')),

  thumb_uri TEXT,                         -- thumbnail file path
  thumb_width INTEGER,                    -- thumbnail width in pixels
  thumb_height INTEGER,                   -- thumbnail height in pixels
  thumb_dtype TEXT,                       -- ex: "image/webp" or "webp"

  -- rtree convenience:
  -- store bbox explicitly (EPSG:4326 lon/lat) so sqlite can index it quickly.
  -- if no bbox during ingest, you can backfill later and rtree will update.
  min_lon REAL,
  min_lat REAL,
  max_lon REAL,
  max_lat REAL,

  -- basic bbox sanity when provided (allow NULLs)
  CHECK (min_lon IS NULL OR max_lon IS NULL OR min_lon <= max_lon),
  CHECK (min_lat IS NULL OR max_lat IS NULL OR min_lat <= max_lat)
);

-- tiles commonly queried by mosaic_id
CREATE INDEX IF NOT EXISTS tile_mosaic_idx
  ON tile_metadata (mosaic_id);

-- prevent duplicates for a mosaic’s tile grid
CREATE UNIQUE INDEX IF NOT EXISTS tile_mosaic_zxy_uk
  ON tile_metadata (mosaic_id, z, x, y);

-- for serving query by z/x/y without mosaic_id 
CREATE INDEX IF NOT EXISTS tile_zxy_idx
  ON tile_metadata (z, x, y);

-- non-spatial index on footprint (won’t speed true spatial ops, but helps get us exact match/debug)
CREATE INDEX IF NOT EXISTS tile_footprint_idx
  ON tile_metadata (footprint);

-- thumbnail-related lookup parity (kept because you had them conceptually)
CREATE INDEX IF NOT EXISTS thumb_mosaic_idx
  ON tile_metadata (mosaic_id);

CREATE INDEX IF NOT EXISTS thumb_zxy_idx
  ON tile_metadata (z, x, y);

CREATE INDEX IF NOT EXISTS thumb_footprint_idx
  ON tile_metadata (footprint);


-- =========================
--    RTREE SPATIAL INDEX
-- =========================
-- sqlite does not have postgis+gist. rtree gives fast bbox overlap filtering.
-- it indexes rectangles: [min_lon,max_lon] x [min_lat,max_lat]
--
-- IMPORTANT:
-- - rtree only indexes rows where bbox columns are non-null
-- - triggers below keep rtree synced automatically
CREATE VIRTUAL TABLE IF NOT EXISTS tile_rtree USING RTREE(
  tile_id,
  min_lon, max_lon,
  min_lat, max_lat
);

-- on insert: only add to rtree if bbox is present
CREATE TRIGGER IF NOT EXISTS tile_rtree_insert
AFTER INSERT ON tile_metadata
WHEN new.min_lon IS NOT NULL AND new.min_lat IS NOT NULL AND new.max_lon IS NOT NULL AND new.max_lat IS NOT NULL
BEGIN
  INSERT into tile_rtree(tile_id, min_lon, max_lon, min_lat, max_lat)
  VALUES (new._id, new.min_lon, new.max_lon, new.min_lat, new.max_lat);
END;

-- on delete: always try to remove (safe even if row never existed in rtree)
CREATE TRIGGER IF NOT EXISTS tile_rtree_delete
AFTER DELETE ON tile_metadata
BEGIN
  DELETE from tile_rtree WHERE tile_id = old._id;
END;

-- on update: if bbox changes rebuild the rtree entry for that tile_id
CREATE TRIGGER IF NOT EXISTS tile_rtree_update_bbox
AFTER UPDATE OF min_lon, min_lat, max_lon, max_lat ON tile_metadata
BEGIN
  DELETE from tile_rtree WHERE tile_id = new._id;

  INSERT into tile_rtree(tile_id, min_lon, max_lon, min_lat, max_lat)
  SELECT new._id, new.min_lon, new.max_lon, new.min_lat, new.max_lat
  WHERE new.min_lon IS NOT NULL AND new.min_lat IS NOT NULL AND new.max_lon IS NOT NULL AND new.max_lat IS NOT NULL;
END;


-- =========================
--       STAGING TABLES
-- =========================
-- staging tables for copying csv into (everything as text), then casting into final tables

CREATE TABLE IF NOT EXISTS mosaic_stage(
  mosaic_id TEXT,       -- csv will input uuid string, generated with ingust
  uri TEXT NOT NULL,
  uri_etag TEXT,
  byte_size TEXT,
  crs TEXT,
  srid TEXT,
  pixel_width TEXT,
  pixel_height TEXT,
  band_count TEXT,
  dtype TEXT,
  nodata TEXT,
  footprint TEXT,
  acquired_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS mosaic_stage_uri_idx
  ON mosaic_stage (uri);

CREATE INDEX IF NOT EXISTS mosaic_stage_mosaic_id_idx
  ON mosaic_stage (mosaic_id);


CREATE TABLE IF NOT EXISTS tile_stage(
  mosaic_id TEXT,       -- if csv already has mosaic_id
  mosaic_uri TEXT,      -- if you want to join by uri to look up mosaic_id

  z TEXT,
  x TEXT,
  y TEXT,

  tile_width TEXT,
  tile_height TEXT,
  overlap TEXT,
  annotation TEXT,

  tile_uri TEXT NOT NULL,
  tile_uri_etag TEXT,

  footprint TEXT,
  nodata_frac TEXT,
  created_at TEXT,

  thumb_uri TEXT,
  thumb_width TEXT,
  thumb_height TEXT,
  thumb_dtype TEXT,

  -- bbox text columns so bbox can load directly from csv
  min_lon TEXT,
  min_lat TEXT,
  max_lon TEXT,
  max_lat TEXT
);

CREATE INDEX IF NOT EXISTS tile_stage_mosaic_id_idx
  ON tile_stage (mosaic_id);

CREATE INDEX IF NOT EXISTS tile_stage_mosaic_uri_idx
  ON tile_stage (mosaic_uri);

