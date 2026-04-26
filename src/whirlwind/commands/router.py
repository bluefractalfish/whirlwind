"""whirlwind.commands.router 


    replaces match blocks for command subcommand parsing 

"""

from dataclasses import dataclass 

from whirlwind.commands.base import Command 
from whirlwind.domain.config.schema import Config 
from whirlwind.ui import face

@dataclass 
class CommandRouter(Command):
    """ routes command group to its subcommands 

        example usage 
        -------------- 

        test ids ./mnt -f 
            --> routes["ids"].run([".mnt","-f"], config)

        test downsample -f 
            ---> routes["downsample"].run(["-f"], config)

    """

    name: str 
    routes: dict[str, Command]

    def run(self, tokens: list[str], config: Config) -> int: 
        if not tokens: 
            face.error(f"usage: {self.name} <subcommand> ")
            return 3 
        subcommand = tokens[0]
        command = self.routes.get(subcommand)

        if command is None:
            face.error(f"{self.name} usage: {subcommand} is an unknown subcommand")
            face.info(f"available: {', '.join(sorted(self.routes.keys()))}")
            return 3 
        return command.run(tokens[1:], config)

