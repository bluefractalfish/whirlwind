"""whirlwind.commands.router 


    replaces match blocks for command subcommand parsing 

"""

from dataclasses import dataclass 

from whirlwind.commands.base import Command 
from whirlwind.commands.bridge import BridgeCommand
from whirlwind.domain.config.schema import Config 
from whirlwind.face import face
from dataclasses import dataclass, field
from collections.abc import Iterable

from whirlwind.commands.base import Command
from whirlwind.commands.bridge import BridgeCommand
from whirlwind.domain.config.schema import Config
from whirlwind.face import face


RouteKey = str | tuple[str, ...]
HELP_FLAGS = {"-h","--help","help"}


@dataclass
class CommandRouter(Command):

    """ 
    routes command group to its subcommands 
        
        example usage 
        -------------- 
        
        CommandRouter(
            name="test",
            routes={
                ("ids","mosaics"): WriteIDManifestCommand,
                ("meta","metadata"): DiscoverCommand, 
                 ...
            }
        )

        test ids ./mnt -f 
            --> routes["ids"].run([".mnt","-f"], config)

        test downsample -f 
            ---> routes["downsample"].run(["-f"], config)

        test downsample -h 
            ----> returns BridgeCommand.help()

    """

    name: str
    routes: dict[RouteKey, BridgeCommand]

    _flat_routes: dict[str, BridgeCommand ] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        flat: dict[str, BridgeCommand] = {}

        for names, command in self.routes.items():
            if isinstance(names, str):
                aliases = (names,)
            else:
                aliases = names

            for alias in aliases:
                key = alias.strip()

                if key in flat:
                    raise ValueError(f"duplicate route alias: {key}")

                flat[key] = command

        self._flat_routes = flat

    def run(self, tokens: list[str], config: Config) -> int:
        if not tokens:
            self.show_help()
            return 0

        subcommand = tokens[0] 

        if len(tokens) > 1 and tokens[1] in HELP_FLAGS:
            return self.show_subcommand_help(subcommand) 

        command = self._flat_routes.get(subcommand)

        if command is None:
            face.error(f"{self.name} usage: {subcommand} is an unknown subcommand")
            face.info(f"available: {', '.join(sorted(self._flat_routes.keys()))}")
            return 3

        return command.run(tokens[1:], config)

    def show_help(self) -> None: 
        face.div()
        face.info(f"usage: {self.name} <subcommand> [options]")
        face.error(f"usage: {self.name} <subcommand>")
        face.div()

    def show_subcommand_help(self, subcommand: str) -> int: 
        command = self.routes.get(subcommand) 

        if command is None: 
            face.div()
            face.error(f"self.name usage: {subcommand} is an unknown subcommand") 
            face.info(f"available: {', '.join(sorted(self._flat_routes.keys()))}")
            return 3 

        face.info(command.help())

        face.info(f"usage: {self.name} {subcommand} [options]")
        return 0 
