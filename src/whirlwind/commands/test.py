
from dataclasses import dataclass
from whirlwind.ui import face 
from whirlwind.commands.base import Command 
from whirlwind.config import Config

#from whirlwind.commands.mosaic import ShardMosaicCommand 
@dataclass
class Test(Command):
    name = "test"

    def run(self, tokens: list[str], config: Config) -> int:
        if len(tokens) == 0:
            return 1
        match tokens[0]:
            case "build":
                return 1
            case "stats":
                return 1
            case _:
                pass
                return 3
    
