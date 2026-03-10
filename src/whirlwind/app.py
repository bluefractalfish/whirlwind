
"""
APP.PY 

owns command registration and dispatch methods
    WhirlwindApp: application container for all command dispatching
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass 
from typing import Dict, Iterable


from .commands.base import Command
from .commands.inspect import InspectCommand
from .commands.ingest import IngestCommand

# WHIRLWIND APP
class WhirlwindApp:
    """Application container for command dispatchers"""
    def __init__(self, commands: Iterable[Command]) -> None:
        self._commands: Dict[str,Command] = {
                    command.name: command for command in commands
                    }
    @property 
    def commands(self) -> List[Command]:
        return list(self._commands.values())

    def run(self,args:argparse.Namespace) -> int:

        cmd_ = getattr(args,"cmd",None)
        if not cmd_:
            return 2
        command = self._commands.get(cmd_)
        if command is None:
            return 2
        return command.run(args)
        
#####################################################
### BUILD APP

def _build() -> WhirlwindApp:
    """create the application with all registered commands"""
    return WhirlwindApp(
            commands=[
                InspectCommand(),
                IngestCommand(),
            ]
        )
