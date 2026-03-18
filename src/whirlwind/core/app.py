from __future__ import annotations

from typing import Dict, Iterable

from ..commands.base import Command
from ..commands.ingest import IngestCommand
from ..commands.inspect import InspectCommand
from ..utils.logger import Logger



class WhirlwindApp:
    def __init__(self, commands: Iterable[Command]) -> None:
        self._commands: Dict[str, Command] = {
            command.name: command for command in commands
        }

    def run(self, tokens: list[str], config: dict) -> int:
        if not tokens:
            return 0

        head = tokens[0]
        command = self._commands.get(head)
        if command is None:
            raise ValueError(f"unknown command: {head}")

        return command.run(tokens[1:], config)


def _build(log) -> WhirlwindApp:
    return WhirlwindApp(
        commands=[
            InspectCommand(),
            IngestCommand(log),
        ]
    )
