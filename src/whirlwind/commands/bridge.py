"""whirlwind.commands.bridge 


command layer utilities for translating user shell inputs into typed BridgeRequests 

tokens + config 
    -> RequestBuilder -> BridgeRequest -> Bridge.run() -> BridgeResult -> Presenter -> exit code  

"""

from whirlwind.domain.config.schema import Config 

from dataclasses import dataclass 
from typing import Generic, Protocol, TypeVar 


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

    example usage: 
    --------------- 
    tokens = ["./mnt","-f","--all"]

    TokenView.parse(tokens) 
        flags = {"-f","--all"}
        args = ["./mnt"]

    """
    flags: set[str]
    args: list[str]

    @classmethod 
    def parse(cls, tokens: list[str]) -> "TokenView":
        return cls(
                flags = {t for t in tokens if t.startswith("-")},
                args = [t for t in tokens if not t.startswith("-")],
                )

    def has(self, *names: str) -> bool:
        return any(name in self.flags for name in names)


    def arg(self, index:int, default: str | None=None) -> str | None:
        if index < len(self.args):
            return self.args[index]
        return default 

    def require(self, index: int, name: str) -> str: 
        value = self.arg(index)
        if value is None:
            raise ValueError(f"missing required argument: {name}")
        return value 


class RequestBuilder(Protocol[RequestType_co]):
    """
        protocol for converting command tokens + config 
        into typed bridge request 

    """
    def from_tokens(self, tokens: list[str], config: Config) -> RequestType_co: 
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
class ABridgeCommand(Generic[RequestType, ResultType]): 
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

    def run(self, tokens: list[str], config: Config) -> int: 
        request = self.builder.from_tokens(tokens, config)
        result = self.bridge.run(request)
        return self.reporter.report(result)

