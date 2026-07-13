from whirlwind.adapters.geo.gdal_env import init_gdal
from whirlwind.entrypoint.app import WhirlwindApp
from whirlwind.entrypoint.shell import WShell 
from whirlwind.domain.config import Config

def bootstrapp(config: Config) -> int:
    init_gdal()

    from whirlwind.commands import Test
    from whirlwind.commands.fronts.operators import (
            RunOperators, 
            BuildOperators, 
            ShardOperators, 

            MosaicOperators, 
            TileOperators, 
            StagingOperators, 
            DatabaseInitOperator, 
            DiscoverOperators, 
            MetamosaicOperators
            ) 

    from whirlwind.commands.shell.shell_nav_cmds import (
            CdCommand, 
            LsCommand, 
            EnvCommand, 
            ViewCommand
            )

    app = WhirlwindApp( cmds=[ 
                              CdCommand(), 
                              LsCommand(),
                              EnvCommand(),
                              ViewCommand(), 

                              Test(), 
                                
                              RunOperators, 
                              BuildOperators,
                              ShardOperators, 
                                
                            # legacy 
                            # DiscoverOperators,   
                            # MosaicOperators, 
                            # TileOperators, 
                            # DatabaseInitOperator, 
                            # MetamosaicOperators
                               
                              ],
        config=config )

    return WShell(app).run()

