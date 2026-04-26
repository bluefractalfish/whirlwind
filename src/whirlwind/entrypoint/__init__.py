
from whirlwind.entrypoint.app import WhirlwindApp
from whirlwind.entrypoint.shell import WShell 
from whirlwind.domain.config import Config

def bootstrapp(config: Config) -> int:

    from whirlwind.commands import Test

    app = WhirlwindApp( cmds=[ 
                              Test()
                              ],
        config=config )

    return WShell(app).run()

