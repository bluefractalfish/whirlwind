from __future__ import annotations

from whirlwind.imps import *
from ..commands.base import Command
from ..commands.ingest import IngestCommand
from ..commands.inspect import InspectCommand
from ..utils.logger import Logger
from ..utils.timer import timed 


class WhirlwindApp:

    def __init__(self, commands: Iterable[Command]) -> None:
        self._commands: Dict[str, Command] = {
            command.name: command for command in commands
        }

        self.run_id="ww"+str(uuid.uuid4())[:5]

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
def _build(log) -> WhirlwindApp:
    return WhirlwindApp(
        commands=[
            InspectCommand(),
            IngestCommand(log),
        ]
    )
