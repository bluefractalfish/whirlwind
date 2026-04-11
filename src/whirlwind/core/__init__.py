
from whirlwind.core.app import WhirlwindApp
from whirlwind.config import Config
from whirlwind.core.shell import WShell 

def bootstrapp(config: Config) -> int:

    from whirlwind.commands import Catalog, Mosaic, Tile, Label, Test
    app = WhirlwindApp( cmds=[ Catalog(),
                              Mosaic(), 
                              Tile(), 
                              Label(),
                              Test()
                              ],
        config=config )

    return WShell(app).run()

