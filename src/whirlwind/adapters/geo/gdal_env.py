from __future__ import annotations

from osgeo import gdal

_INITIALIZED = False


def init_gdal() -> None:
    global _INITIALIZED

    if _INITIALIZED:
        return

    gdal.UseExceptions()
    _INITIALIZED = True
