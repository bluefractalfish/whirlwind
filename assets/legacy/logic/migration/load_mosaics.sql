\set ON_ERROR_STOP on


begin;

-- upsert into final mosaic
insert into mosaic (
  uri, uri_etag, byte_size, crs, srid,
  pixel_width, pixel_height, band_count, dtype, nodata,
  footprint, acquired_at
)
select
  ms.uri,
  nullif(ms.uri_etag, ''),
  nullif(ms.byte_size, '')::bigint,
  nullif(ms.crs, ''),
  nullif(ms.srid, '')::integer,
  nullif(ms.pixel_width, '')::integer,
  nullif(ms.pixel_height, '')::integer,
  nullif(ms.band_count, '')::integer,
  nullif(ms.dtype, ''),
  nullif(ms.nodata, '')::double precision,
  st_multi(st_setsrid(st_geomfromewkt(ms.footprint),4326))::geometry(multipolygon, 4326),
  nullif(ms.acquired_at, '')
from mosaic_stage ms
on conflict (uri) do update set
  uri_etag     = excluded.uri_etag,
  byte_size    = excluded.byte_size,
  crs          = excluded.crs,
  srid         = excluded.srid,
  pixel_width  = excluded.pixel_width,
  pixel_height = excluded.pixel_height,
  band_count   = excluded.band_count,
  dtype        = excluded.dtype,
  nodata       = excluded.nodata,
  footprint    = excluded.footprint,
  acquired_at  = excluded.acquired_at;

commit;

