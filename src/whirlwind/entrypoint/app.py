
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

from typing import Dict, Iterable, List

from whirlwind.commands.base import Command 
#from whirlwind.commands.wrangle import WrangleCommand
from whirlwind.tools.ids import gen_run_id 
#from whirlwind.ui import face 

from whirlwind.domain.config import Config 

class WhirlwindApp:

    def __init__(self, cmds: Iterable[Command], config: Config) -> None:
        self._commands: Dict[str, Command] = {c.name: c for c in cmds}
        self.run_id = gen_run_id() 
        self.config = config 

    def run(self, tokens: list[str]) -> int:
        """
        takes in a list of tokens and config 
        if tokens exist check first word for commands
        """
        if not tokens:
            return 3
        head = tokens[0]
        command = self._commands.get(head)
        if command is None:
            return 11

        return command.run(tokens[1:], self.config)

    def _help(self) -> List[dict[str,str]]:
        return [command.help() for command in self._commands.values()]

        

