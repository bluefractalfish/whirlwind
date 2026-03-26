""" whirlwind.commands.ingest 
    
    PURPOSE:
        - `ingest` command family: (mosaics (legacy tiles), shards)

    BEHAVIOR:
        - validate tokens and select subcommand 
        - delegate to ingest pipeline in whirlwind.ingest 
        - print conside human output for interactive use 
    PUBLIC:
        - IngestCommand 

"""
