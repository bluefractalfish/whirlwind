"""whirlwind.io.shards 


    PURPOSE:
        - write tile payloads into tar shards 
    BEHAVIOR:
        - create sequential tar files <prefix>-NNN.tar 
        - write two entries per tile <tile_id>.npy and <tile_id>.json 
        - rotate to next shard after shard_size samples 
    PUBLIC:
        - ShardWriter 
        
"""
