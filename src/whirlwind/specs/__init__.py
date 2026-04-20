"""whirlwind.specs 

PURPOSE:
        - entrypoint for all specs 
BEHAVIOR:
        - specs serves as communication layers between ports (objects) and interfaces 
        - 
"""



from whirlwind.specs.downsample import DSSpec, DSParams
from whirlwind.specs.tiling import TSpec 
from whirlwind.specs.quant import QSpec 
from whirlwind.specs.shard import ShardSpec
