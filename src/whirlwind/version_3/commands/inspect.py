"""whirlwind.commands.inspect 

    PURPOSE:
        - `inspect` command: scan a directory and generate metadata csv 
    BEHAVIOUR:
        - validate command tokens and resolve path 
        - generate deterministic metadata csv name using fingerpreint of input dir 
        - create csv if not present 
        - print simple scan summary 
        - keeps geospatial extraction and CSV writting to lower layers (geo/io)
    PUBLIC: 
        - InspectCommand 
"""
