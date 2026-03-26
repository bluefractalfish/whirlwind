""" whirlwind.io.metadata 

    PURPOSE: 
        - write directory level mosaic metadata CSVs 
    BEHAVIOR:
        - recursively find files under input directroy 
        - extract metadata for each file via geo.metadata.extract_metadata 
        - write CSV under output 
    PUBLIC:
        - write_metadata(input_dir, out_csv, columns)

"""

