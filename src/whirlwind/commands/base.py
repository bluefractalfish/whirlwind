"""
    Command(ABC) class forms base interface for all w: commands.
"""

from whirlwind.imps import *
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
