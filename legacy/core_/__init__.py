
from whirlwind.core.app import WhirlwindApp
from whirlwind.domain.config import Config
from whirlwind.core.shell import WShell 

def bootstrapp(config: Config) -> int:

    from whirlwind.commands import Test

    app = WhirlwindApp( cmds=[ 
                              Test()
                              ],
        config=config )

    return WShell(app).run()

