
from whirlwind._r.core_r.app import WhirlwindApp
from whirlwind._r.config_r import Config
from whirlwind._r.core_r.shell import WShell 

def bootstrapp(config: Config) -> int:

    from whirlwind._r.commands_r import Catalog, Mosaic, Tile, Label 
    app = WhirlwindApp( cmds=[ Catalog(), Mosaic(), Tile(), Label(),],
        config=config )

    return WShell(app).run()

