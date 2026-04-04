"""whirlwind.commands.base 
    
    PURPOSE: 
        - command interface for interactive shell dispatcher 

    BEHAVIOR: 
        - define consistent run/help protocols for Commands 

    PUBLIC:
        - Command(ABC)

"""
from typing import Any, List 
from abc import ABC, abstractmethod
from whirlwind._r.config_r import Config


class Command(ABC):
    """base interface for all commands"""
    name: str

    @abstractmethod
    def run(self, tokens: list[str], config: Config) -> int:
        raise NotImplementedError
    
    def help(self) -> dict[str,str]:
        ...

class ShellCommand(ABC):
    """ base interface for all shell commands. includes multiple names"""
    names: List[str] 

    @abstractmethod 
    def run(self, tokens: list[str], _config: dict[str,Any] | None=None) -> int:
        raise NotImplementedError 
    def help(self) -> dict[str,str]:
        raise NotImplementedError
