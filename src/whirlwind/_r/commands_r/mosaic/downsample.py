
from typing import List, Dict, Any 
from whirlwind.wrangler.downsample import downsample_mosaic
from whirlwind._r.commands_r import Command 
from whirlwind._r.config_r import Config 



class DownsampleCommand(Command):
    name = "downsample"

    def run(self, tokens: List[str], config: Config) -> int:
        return 999
        

