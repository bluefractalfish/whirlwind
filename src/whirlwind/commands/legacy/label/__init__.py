
def _add_text_field(layer, name: str, width: int = 128) -> None:
    fd = ogr.FieldDefn(name, ogr.OFTString)
    fd.SetWidth(width)
    layer.CreateField(fd)

def _add_real_field(layer, name: str) -> None:
    fd = ogr.FieldDefn(name, ogr.OFTReal)
    layer.CreateField(fd)

def stage_label_gpkg(gpkg_path: Path, epsg: int | None = None) -> None:
    gpkg_dest = gpkg_path/"path_vectors.gpkg"
    drv = ogr.GetDriverByName("GPKG")
    ds = drv.CreateDataSource(gpkg_dest)
    if ds is None:
        raise RuntimeError(f"Could not create GeoPackage: {gpkg_path}")

    srs = None
    if epsg is not None:
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(epsg)

    path_layer = ds.CreateLayer("damage_path", srs=srs, geom_type=ogr.wkbLineString)
    area_layer = ds.CreateLayer("damage_area", srs=srs, geom_type=ogr.wkbPolygon)

    for lyr in (path_layer, area_layer):
        _add_text_field(lyr, "event_id", 64)
        _add_text_field(lyr, "label", 64)
        _add_real_field(lyr, "confidence")
        _add_text_field(lyr, "notes", 255)

    ds = None
