from typing import Any 
from dataclasses import dataclass 
from whirlwind.interface import face 
from whirlwind.domain.config.schema import Config 
from whirlwind.commands.bridge import BridgeCommand

@dataclass(frozen=True)
class InitStep:
    name: str
    command: BridgeCommand[Any, Any]
    tokens: tuple[str, ...] = ()
    required: bool = True
    forward_force: bool = True

@dataclass(frozen=True)
class Request:
    config: Config
    force: bool
    steps: tuple[InitStep, ...]


@dataclass(frozen=True)
class StepResult:
    name: str
    code: int


@dataclass(frozen=True)
class Result:
    steps: tuple[StepResult, ...]
    code: int

class DatabaseInitBridge:
    def run(self, request: Request) -> Result:
        results: list[StepResult] = []

        for step in request.steps:
            face.header(f"database init: {step.name}")

            step_tokens = list(step.tokens)

            if request.force and step.forward_force:
                step_tokens.append("-f")

            code = step.command.run(step_tokens, request.config)

            results.append(
                StepResult(
                    name=step.name,
                    code=code,
                )
            )

            if code != 0 and step.required:
                return Result(
                    steps=tuple(results),
                    code=code,
                )

        return Result(
            steps=tuple(results),
            code=0,
        )
