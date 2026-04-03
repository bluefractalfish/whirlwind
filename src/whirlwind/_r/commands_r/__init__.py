"""whirlwind.commands 
    
PURPOSE:
    - front end for all whirlwind commands 
BEHAVIOR:
    - instantiates Catalog, Mosaic, Tile, Label 
    - defines run(tokens, config)

PUBLIC:
    Catalog 
    Mosaic 
    Tile 
    Label 
"""


from dataclasses import dataclass
from whirlwind.ui import face 
from whirlwind._r.commands_r.base import Command 
from whirlwind._r.config_r import Config

from whirlwind._r.commands_r.catalog import BuildCommand, StatsCommand
#from whirlwind._r.commands_r.mosaic import DownsampleCommand

@dataclass
class Catalog(Command):
    name = "catalog"

    def run(self, tokens: list[str], config: Config) -> int:
        """ 
            valid commands for catalog: 
            catalog build 
            catalog stats 
            catalog 
        """
        if len(tokens) == 0:
            sr = StatsCommand().run(tokens[1:],config)
            br = BuildCommand().run(tokens[1:],config)
            return sr+br
        match tokens[0]:
            case "build":
                return BuildCommand().run(tokens[1:], config)
            case "stats":
                return StatsCommand().run(tokens[1:],config)
            case _:
                face.error(f"catalog usage: {tokens[0]} not a valid command")
                return 3
    
class Mosaic(Command):
    name = "mosaic"

    def run(self, tokens: list[str], config: Config) -> int:
        if len(tokens) == 0:
            face.error("mosaic usage: mosaic expects at least one subcommand")
        match tokens[0]:
            case "downsample" | "ds":
                return DownsampleCommand().run(tokens[1:],config)
            case "info":
                face.error("command not yet built")
                return 4

        return 0

class Tile(Command): 
    name = "tile"

    def run(self, tokens: list[str], config: Config) -> int:
        return 0

class Label(Command): 
    name = "label"

    def run(self, tokens: list[str], config: Config) -> int:
        return 0
