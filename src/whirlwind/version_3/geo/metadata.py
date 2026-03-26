"""whirlwind.geo.metadata 

    PURPOSE:
        - extract metadata from raster mosaics using gdal 
    BEHAVIOR:
        - open raster via gdal and return selected metadata fields 
        - compute lightweight geospatial descriptors 
    PUBLIC:
        - extract_metadata(uri, columns) -> dict[str, Any]

"""
