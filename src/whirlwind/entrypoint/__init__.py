from whirlwind.adapters.geo.gdal_env import init_gdal
from whirlwind.entrypoint.app import WhirlwindApp
from whirlwind.entrypoint.shell import WShell 
from whirlwind.domain.config import Config

def bootstrapp(config: Config) -> int:
    init_gdal()

    from whirlwind.commands import Test
    from whirlwind.commands.fronts.operators import (
            MosaicOperators, TileOperators, StagingOperators, DatabaseInitOperator, DiscoverOperators
            )

    app = WhirlwindApp( cmds=[ 
                              Test(), 
                              DiscoverOperators, 
                              MosaicOperators, 
                              TileOperators, 
                              StagingOperators, 
                              DatabaseInitOperator
                              ],
        config=config )

    return WShell(app).run()

