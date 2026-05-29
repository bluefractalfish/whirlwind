
from dataclasses import dataclass
from whirlwind.commands.base import Command
from whirlwind.commands.bridge import BridgeCommand
from whirlwind.domain.config.schema import Config
from whirlwind.interface import face

HELP_FLAGS = {"-h", "--help", "help"}


@dataclass(frozen=True)
class CommandStep:
    name: str
    command: BridgeCommand
    tokens: tuple[str, ...] = ()
    required: bool = True


@dataclass
class DatabaseInitCommand(Command):
    name: str
    steps: tuple[CommandStep, ...]

    def help(self) -> str:
        step_lines = "\n".join(f"  {step.name}" for step in self.steps)

        return f"""
    usage: database init [options]

    purpose:
      Initialize a WHIRLWIND database run tree by running the standard setup commands.

    options:
      -f, --force
          Forward overwrite/force behavior to steps that support it.

      -h, --help
          Show this help.

    steps:
    {step_lines}

    examples:
      database init
      database init -f
    """.strip()

    def run(self, tokens: list[str], config: Config) -> int:
        if tokens and tokens[0] in HELP_FLAGS:
            face.info(self.help())
            return 0

        force = "-f" in tokens or "--force" in tokens
        display = "-d" in tokens or "--display" in tokens

        for step in self.steps:
            face.header(f"database init: {step.name}")

            step_tokens = list(step.tokens)

            if force:
                step_tokens.append("-f")

            if display: 
                step_tokens.append("-d")

            code = step.command.run(step_tokens, config)

            if code != 0 and step.required:
                face.error(f"database init failed at step: {step.name}")
                return code

        face.info("database init complete")
        return 0
