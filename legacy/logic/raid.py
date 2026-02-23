# raid.py   ---> defeat the bugs

from pathlib import Path
import importlib
import pytest

def _import_toolbox():
    """
    Import toolbox.py and give a *clear* failure
    """
    try:
        return importlib.import_module("toolbox")
    except SyntaxError as e:
        pytest.fail(
            f"SyntaxError importing toolbox.py at line {e.lineno}:{e.offset}\n"
            f"{e.msg}\n"
            f"Fix toolbox.py syntax/indentation first, then re-run pytest.\n"
        )
    except Exception as e:
        pytest.fail(f"Failed importing toolbox.py: {type(e).__name__}: {e}")


def test_iter_tifs_finds_tifs(tmp_path: Path):
    toolbox = _import_toolbox()

    # Arrange: nested directory with tif/tiff + non-tif
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "b").mkdir(parents=True, exist_ok=True)

    (tmp_path / "a" / "one.tif").write_text("x", encoding="utf-8")
    (tmp_path / "a" / "b" / "two.tiff").write_text("y", encoding="utf-8")
    (tmp_path / "a" / "b" / "nope.jpg").write_text("z", encoding="utf-8")

    # Act
    found = sorted([p.name for p in toolbox.iter_tifs(tmp_path)])

    # Assert
    assert found == ["one.tif", "two.tiff"]


def test_parse_aquired_at_yymmdd_filename():
    toolbox = _import_toolbox()

    p = Path("240119_denver_anything.tif")
    got = toolbox.parse_aquired_at(p, valid=True)

    assert got == "2024-01-19"


def test_get_srid_epsg4326():
    toolbox = _import_toolbox()

    osgeo = pytest.importorskip("osgeo")
    osr = osgeo.osr

    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    crs_wkt = srs.ExportToWkt()

    got = toolbox.get_srid(crs_wkt)
    assert str(got) == "4326"

def test_get_raster_shape_from_small_geotiff(tmp_path: Path):
    toolbox = _import_toolbox()

    osgeo = pytest.importorskip("osgeo")
    gdal = osgeo.gdal
    osr = osgeo.osr

    tif = tmp_path / "small.tif"

    # Create a tiny raster: 7x5 pixels, 1 band
    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create(str(tif), 7, 5, 1, gdal.GDT_Byte)
    assert ds is not None

    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    ds.SetProjection(srs.ExportToWkt())

    ds.FlushCache()
    ds = None

    ds2 = gdal.Open(str(tif), gdal.GA_ReadOnly)
    assert ds2 is not None

    pixel_width, pixel_height, band_count = toolbox.get_raster_shape(ds2)

    assert pixel_width == "7"
    assert pixel_height == "5"
    assert band_count == "1"


