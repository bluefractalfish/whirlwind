
"""whirlwind.commands.entries
    
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
from whirlwind.commands.base import Command 
from whirlwind.config import Config

from whirlwind.commands.catalog import BuildCommand, StatsCommand
from whirlwind.commands.mosaic import DownsampleCommand
#from whirlwind.commands.mosaic import ShardMosaicCommand 
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
        
        """ 
            valid commands for mosaic:
            mosaic downsample | ds 
            mosaic shard | t --> cuts mosaic and emits webdataset. 
                                         for each tile, access same logic as: 
                                            tile read --> window read 
                                            tile label --> labels against label build output 
                                            tile quantize --> runs quantization if needed 
                                            tile write   ---> writes webdatashard 

            mosaic info

               
        """

        if len(tokens) == 0:
            face.error("mosaic usage: mosaic expects at least one subcommand")
        match tokens[0]:
            case "downsample" | "ds":
                return DownsampleCommand().run(tokens[1:],config)
            case "shard" | "s":
                return ShardMosaicCommand().run(tokens[1:],config)
            case "info":
                face.error("command not yet built")
                return 4

        return 0

class Tile(Command): 
    name = "tile"

    def run(self, tokens: list[str], config: Config) -> int:
        """ 
            expects: 
                       <operation> <mosaic_id> <column> <row> 

        """
        if len(tokens) == 0:
            face.error("tile usage: expects at least one subcommand")
        match tokens[0]:
            case "quantize":
                ...
                #return QuantizeTile().run(tokens[1:],config)
                # returns quantized tile bytes? check efficiency 
            case "read":
                ... 
                #return ReadTileCommand().run(tokens[1:], config)
            case "label":
                ... 
                #return LabelTileCommand().run(tokens[1:],config)
        return 0

class Label(Command): 
    name = "label"


    def run(self, tokens: list[str], config: Config) -> int:
        if len(tokens) == 0:
            face.error("label usage: expects at least one subcommand")
        match tokens[0]:
            case "stage":
                ... 
                #return StageLabelCommand().run(tokens[1:],config)
            case "intersect":
                ... 
                #return IntersectCommand().run(tokens[1:].config)

        return 0



"""     
        run pipeline = > catalog build | label init | label build | mosaic tesselate 

                    builds catalog,
                    reads catalog to generate browse mosaics 
                     label stage 
                            -> user annotates with path data 
                    label intersect --> uses tiling scheme to check intersection 
                                    with label metadata builds metadata for each mosaic and each tile 
                    mosaic shard  

""" 
