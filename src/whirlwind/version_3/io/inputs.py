"""whirlwind.io.inputs 
    
    PURPOSE:
        - resolve an input selector (csv, directory, glob)
        - iterate raster uris 
    BEHAVIOR:
        - csv: read a uri column from metadata file 
        - directory: recursively yield files with ext = DEFAULT (.tif,.tiff)
        - glob: yield matching files 
    PUBLIC:
        - iterate_uris(source, extensions)

"""
