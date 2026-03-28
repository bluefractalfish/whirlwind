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



class Command(ABC):
    """base interface for all commands"""
    name: str

    @abstractmethod
    def run(self, tokens: list[str], config: dict[str,Any]) -> int:
        raise NotImplementedError
    
    def help(self) -> dict[str,str]:
        raise NotImplementedError


class ShellCommand(ABC):
    """ base interface for all shell commands """
    names: List[str] 

    @abstractmethod 
    def run(self, tokens: list[str]) -> int:
        raise NotImplementedError 
    def help(self) -> dict[str,str]:
        raise NotImplementedError
