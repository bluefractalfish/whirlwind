
""" whirlwind.core.app

    PURPOSE: 
        - application command registry and dispatcher 
    BEHAVIOR: 
        - register commands and dispatch parsed tokens to correct command 
    PUBLIC:
        - WhirlwindApp 
        - build_app(log)
            - add commands here 

"""

from __future__ import annotations 

import uuid 
from typing import Any, Dict, Iterable, List, Optional 

from whirlwind.commands.base import Command 
from whirlwind.core.interfaces import LoggerProtocol, NullLoger 
from whirlwind.tools.timer import timed 
from whirlwind.tools.ids import generate_run_id 


class WhirlwindApp:

    def __init__(self, commands: Iterable[Command]) -> None:
        self._commands: Dict[str, Command] = {command.name: c for c in cmds}

        self.run_id = generate_run_id() 

    @timed("running app")
    def run(self, tokens: list[str], config: dict) -> int:
        if not tokens:
            return 3

        head = tokens[0]
        command = self._commands.get(head)
        if command is None:
            return 3

        return command.run(tokens[1:], config)

    def _help(self) -> List[dict[str,str]]:
        return [command.help() for command in self._commands.values()]

        

@timed("building app")
def build_app(log) -> WhirlwindApp:
    return WhirlwindApp(
        commands=[
            InspectCommand(log.child("inspect")),
            IngestCommand(log.child("ingest")),
        ]
    )
