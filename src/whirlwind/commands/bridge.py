"""whirlwind.commands.bridge 


command layer utilities for translating user shell inputs into typed BridgeRequests 

tokens + config 
    -> RequestBuilder -> BridgeRequest -> Bridge.run() -> BridgeResult -> Presenter -> exit code  

"""

from whirlwind.domain.config.schema import Config 

from dataclasses import dataclass 
from typing import Generic, Protocol, TypeVar, runtime_checkable 


HELP_FLAGS = {"--h","-help"} 

@runtime_checkable 
class Helpable(Protocol):
    def help(self) -> str: 
        ...


# accepts and returns T -> invariant 
RequestType = TypeVar("RequestType")
ResultType = TypeVar("ResultType")

# returns T only -> covariant 
RequestType_co = TypeVar("RequestType_co", covariant=True)
ResultType_co = TypeVar("ResultType_co", covariant=True)

# accepts T only -> contravariant 
RequestType_contra = TypeVar("RequestType_contra", contravariant=True)
ResultType_contra = TypeVar("ResultType_contra", contravariant=True)


@dataclass(frozen=True)
class TokenView: 
    """ 
    lightweight parsed view of shell tokens 
    supports: 
    ---------------
    positional args:
            ./mnt

        boolean flags:
            -f
            --force

        key-value options:
            --mosaic=m-240119-DSM-a31f
            --variant=DSM
            --date=240119
            --metamosaic=mm-denver-a91f2c

    example usage: 
    --------------- 
    tokens = ["./mnt","-f","--all"]

    TokenView.parse(tokens) 
        flags = {"-f","--all"}
        args = ["./mnt"]

    """
    flags: set[str]
    args: list[str]
    options: dict[str, list[str]]

    @classmethod 
    def parse(cls, tokens: list[str]) -> "TokenView":
        flags: set[str] = set()
        args: list[str] = []
        options: dict[str, list[str]] = {}

        for token in tokens:
            if token.startswith("--") and "=" in token:
                key, value = token.split("=", 1)
                options.setdefault(key, []).append(value)

            elif token.startswith("-") or token.startswith("--"):
                flags.add(token)

            else:
                args.append(token)

        return cls(
                flags = flags,
                args = args,
                options = options 
                )

    def has(self, *names: str) -> bool:
        return any(name in self.flags for name in names)

    def values(self, *names: str) -> list[str]:
        out: list[str] = []
        for name in names:
            for value in self.options.get(name, []):
                out.extend(self._csv_values(value))
        return out

    def value(self, name: str, default: str | None = None) -> str | None:
        values = self.options.get(name, [])
        if not values:
            return default
        return values[-1]

    def arg(self, index:int, default: str | None=None) -> str | None:
        if index < len(self.args):
            return self.args[index]
        return default 

    def require(self, index: int, name: str) -> str: 
        value = self.arg(index)
        if value is None:
            raise ValueError(f"missing required argument: {name}")
        return value 
    
    @staticmethod
    def _csv_values(value: str) -> list[str]:
        return [
                part.strip()
                for part in value.split(",")
                if part.strip()
            ]
      

class RequestBuilder(Protocol[RequestType_co]):
    """
        protocol for converting command tokens + config 
        into typed bridge request 

    """
    def from_tokens(self, tokens: list[str], config: Config) -> RequestType_co: 
        ...

    def help(self) -> str: 
        ...

class Bridge(Protocol[RequestType_contra, ResultType_co]):
    """
        intermediate layer recieving typed requests, 
        calling adapters, returns typed result 
    """
    
    def run(self, request: RequestType_contra) -> ResultType_co:
        ... 

class ResultReporter(Protocol[ResultType_contra]): 
    """ 
        converts a bridge result into user facing output 
        and exit code. keeps all ui above bridge 
    """

    def report(self, result: ResultType_contra) -> int: 
        ... 

@dataclass 
class BridgeCommand(Generic[RequestType, ResultType]): 
    """ 
        generic command wrapper 

        ABridgeCommand follows: 
            request = builder.from_tokens(tokens, config)
            result = bridge.run(request)
            return reporter.report(result)
    """
    name: str 
    builder: RequestBuilder[RequestType]
    bridge: Bridge[RequestType, ResultType]
    reporter: ResultReporter[ResultType]
    
    def help(self) -> str: 
        if isinstance(self.builder, Helpable): 
            return self.builder.help()
        return f"usage: {self.name} [options]"

    def run(self, tokens: list[str], config: Config) -> int: 
        if tokens and tokens[0] in HELP_FLAGS: 
            from whirlwind.face import face 
            face.info(self.help())
            return 0 

        request = self.builder.from_tokens(tokens, config)
        result = self.bridge.run(request)
        return self.reporter.report(result)

